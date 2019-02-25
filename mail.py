#!/usr/bin/python
# -*- coding:utf-8 -*-
################################################################################
#
# Copyright (c) 2019 ***.com, Inc. All Rights Reserved
# Copyright 2019, The NSH Anti-Plugin Project
################################################################################
"""
NSH脚本异常用户ID -- 邮件读取和存储MySQL
使用Mac OS的定时工具Launchctl，每天定时读取包含指定关键词的邮件，解析内容，并上传结果至MySQL

Usage: Launchctl定时任务文件(/Users/zhoujl/Library/LaunchAgents/com.mail.plist)
    Step 1: 加载任务, 开启定时
        launchctl load -w com.mail.plist        # 加载任务, -w选项会将plist文件中无效的key覆盖掉，建议加上
        launchctl unload -w com.mail.plist      # 删除任务, 每次修改com.mail.plist后，需在unload并重新load
    Step 2: 确认任务是否加载
        launchctl list | grep 'com.mail'        # 查看任务列表
    Step 3: 直接开始任务, 用于测试
        launchctl start com.mail.plist          # 开始任务(立即执行，可用于测试)
        launchctl stop com.mail.plist           # 结束任务
Authors: Zhou Jialiang
Email: zjl_sempre@163.com
Date: 2019/02/13
"""

import os
import sys
import re
import json
import codecs
import logging
import imaplib
import email
import pymysql
from sshtunnel import SSHTunnelForwarder
from config import SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, SSH_PKEY, LOCAL_HOST
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
from config import MAIL_ACCOUNT, MAIL_PASSWORD, KEY_WORD_SUBJECT, IMAP_HOST, IMAP_PORT
import log
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())     # 更改输出流编码为UTF-8

# 项目路径
PROJECT_DIR = '/Users/zhoujl/workspace/***/online_mail'

# Query to insert row into database nsh_evaluate
QUERY_SQL_INSERT = """
INSERT INTO anti_plugin.nsh_ids_scripts(role_id, ts_start, ts_end) 
VALUES ({role_id}, '{ts_start}', '{ts_end}')
"""

def parse(msg):
    """解析内容
    解析时间段ts以及对应的脚本异常用户ID列表

    Args:
        msg: 待解析的email类

    Return:
        ts: 时间段
        ids: 脚本异常用户ID列表
    """
    ts = ''
    ids = list()
    for part in msg.walk():
        if not part.is_multipart():
            txt = part.get_payload(decode=True).decode('utf-8')

            # 提取时间段
            re_ts_script = re.compile('<font color=\'red\'>(.*?)年(.*?)月(.*?)日(.*?):(.*?)到(.*?)年(.*?)月(.*?)日(.*?):(.*?)</font>')
            ts = '_'.join(re_ts_script.search(txt).groups())

            # 提取ids
            re_ids_script = re.compile(r'疑似作弊玩家统计：</h3>(.*?)<h3>报错编号')
            ids = re_ids_script.search(txt).groups()[0].split()

    return ts, ids


def match(conn, idx_start=800):
    """匹配邮件
    根据邮件主题，匹配关键字，解析内容

    Args:
        conn: 邮箱连接
        idx_start: 扫描邮箱邮件的起始索引

    Yield:
        ts: 时间段
        ids: 时间段对应的脚本异常用户ID
        i: 邮件对应索引
    """
    # 获取收件箱
    INBOX = conn.select('INBOX')
    type, data = conn.search(None, 'ALL')
    mail_list = data[0].split()
    # 遍历邮件
    for i in range(int(idx_start), len(mail_list)):
        logging.info(i)
        # 获取第idx份邮件并解析内容
        type, mail = conn.fetch(mail_list[i], '(RFC822)')
        msg = email.message_from_string(mail[0][1].decode('utf-8'))

        # 获取邮件主题
        subject_encoded, enc = email.header.decode_header(msg.get('subject'))[0]
        try:
            subject_decoded = subject_encoded.decode(enc)
        except Exception as e:
            subject_decoded = subject_encoded

        # 匹配关键字，解析ts和ids
        if KEY_WORD_SUBJECT in subject_decoded:
            logging.info('Index: {}, Subject: {}'.format(i, subject_decoded))
            try:
                ts, ids = parse(msg)
                yield ts, ids, i
            except Exception as e:  # 一些非目标邮件会解析失败，直接忽略即可
                logging.warning('Parse faild. {}'.format(e))



class MysqlDB(object):
    """MySQL类
    连接MySQL，用于上传数据
    """
    def __init__(self, host, port, user, passwd, db):
        self._conn = pymysql.connect(host=host, port=port, user=user, password=passwd, database=db)
        logging.info('Init')

    def __del__(self):
        self._conn.close()

    # 单行插入操作
    def _insert_row(self, sql):
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql)
            self._conn.commit()
        except:
            self._conn.rollback()

    # 批量上传
    def upload_ids(self, sql_base, ids, ts_start, ts_end):
        for role_id in ids:
            sql = sql_base.format(role_id=role_id, ts_start=ts_start, ts_end=ts_end)
            self._insert_row(sql)


if __name__ == '__main__':

    # logging
    log.init_log(os.path.join(PROJECT_DIR, 'logs', 'mail'))

    #连接邮箱，登录
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(MAIL_ACCOUNT, MAIL_PASSWORD)
    logging.info('Successfully connect to mail account: {}!'.format(MAIL_ACCOUNT))

    # SSH隧道连接MySQL, 借用服务器persona11作为跳板，
    # 使得可以在本地处于非公司网络环境下，仍然可以访问MySQL
    with SSHTunnelForwarder(ssh_address_or_host=(SSH_HOST, SSH_PORT),
                            ssh_password=SSH_PASSWORD,
                            ssh_username=SSH_USER,
                            ssh_pkey=SSH_PKEY,
                            remote_bind_address=(MYSQL_HOST, MYSQL_PORT)) as server:

        db = MysqlDB(host=LOCAL_HOST,
                     port=server.local_bind_port,
                     user=MYSQL_USER,
                     passwd=MYSQL_PASSWORD,
                     db=MYSQL_DB)


        # 判断是否已经上传
        ts_uploaded_file = os.path.join(PROJECT_DIR, 'ts_uploaded.json')
        ts_list = list()
        try:
            logging.info('Reading ts list from file {}'.format(ts_uploaded_file))
            with open(ts_uploaded_file, 'r') as f:
                ts_list = json.load(f)
        except Exception as e:
            logging.error('Fail to load ts_uploaded, {}'.format(e))
            raise e


        # 遍历每一封匹配的邮件，解析并上传数据
        for ts, ids, idx in match(conn, idx_start=0):
            ts_start = '-'.join(ts.split('_')[0:3]) + ' ' + ':'.join(ts.split('_')[3:5])
            ts_end = '-'.join(ts.split('_')[5:8]) + ' ' + ':'.join(ts.split('_')[8:])
            ts_record = ts_start + ',' + ts_end

            # 若未上传，则保存至MySQL
            if ts_record not in ts_list:
                logging.info('Start uploading ids with [{ts_start}] ~ [{ts_end}] to MySQL...'.format(ts_start=ts_start, ts_end=ts_end))
                try:
                    db.upload_ids(sql_base=QUERY_SQL_INSERT, ids=ids, ts_start=ts_start, ts_end=ts_end)
                    logging.info('{} ids uploaded...'.format(len(ids)))
                except Exception as e:
                    logging.error('Uploading failed, {}'.format(e))

                # 记录已上传的时间段
                ts_list.append(ts_record)
                with open(ts_uploaded_file, 'w') as f:
                    json.dump(ts_list, f, indent=4)
