#!/usr/bin/python
# -*- coding:utf-8 -*-
__author__ = "Jialiang Zhou"
__copyright__ = "Copyright 2019, The *** Project"
__version__ = "1.0.0"
__email__ = "***"
__phone__ = "***"
__description__ = ""
__usage__ = ""

import os
import sys
import re
import codecs
import imaplib
import email
import pymysql
from sshtunnel import SSHTunnelForwarder
from config_private import SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, SSH_PKEY, LOCAL_HOST
from config_private import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
from config_private import MAIL_ACCOUNT, MAIL_PASSWORD, KEY_WORD_SUBJECT, IMAP_HOST, IMAP_PORT

sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Query to insert row into database nsh_evaluate
QUERY_SQL_INSERT = """
INSERT INTO anti_plugin.nsh_ids_scripts(role_id, ts_start, ts_end) 
VALUES ({role_id}, '{ts_start}', '{ts_end}')
"""

def parse(msg):
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
    # 获取收件箱
    INBOX = conn.select('INBOX')
    type, data = conn.search(None, 'ALL')
    mail_list = data[0].split()
    # 遍历邮件
    for i in range(int(idx_start), len(mail_list)):
        # try:
            print(i)
            # 获取第idx份邮件并解析内容
            type, mail = conn.fetch(mail_list[i], '(RFC822)')
            msg = email.message_from_string(mail[0][1].decode('utf-8'))

            # 获取邮件主题
            subject_encoded, enc = email.header.decode_header(msg.get('subject'))[0]
            subject_decoded = subject_encoded.decode(enc)

            # 匹配关键字，解析ts和ids
            if KEY_WORD_SUBJECT in subject_decoded:
                print('Index: {}, Subject: {}'.format(i, subject_decoded))
                ts, ids = parse(msg)
                yield ts, ids, i
        # except Exception as e:
        #     print('Cannot read No. {} in mail_list. {}'.format(i, e))


# MySQL类
class MysqlDB(object):
    def __init__(self, host, port, user, passwd, db):
        self._conn = pymysql.connect(host=host, port=port, user=user, password=passwd, database=db)
        print('Init')

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
        print('Start uploading ids with [{ts_start}] ~ [{ts_end}] to MySQL...'.format(ts_start=ts_start, ts_end=ts_end))
        for role_id in ids:
            sql = sql_base.format(role_id=role_id, ts_start=ts_start, ts_end=ts_end)
            self._insert_row(sql)
        print('{} ids uploaded...'.format(len(ids)))


if __name__ == '__main__':


    #连接邮箱，登录
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(MAIL_ACCOUNT, MAIL_PASSWORD)
    print('Successfully connect to mail accout: {}!'.format(MAIL_ACCOUNT))

    # SSH隧道连接MySQL
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
        idx_last = 0
        ts_list = list()
        if os.path.exists('ts_upload'):
            with open('ts_upload', 'r') as f:
                for line in f:
                    idx, ts_record = line.strip().split(': ')
                    ts_list.append(ts_record)
                    idx_last = idx

        for ts, ids, idx in match(conn, idx_start=900):
            print(db._conn)
            ts_start = '-'.join(ts.split('_')[0:3]) + ' ' + ':'.join(ts.split('_')[3:5])
            ts_end = '-'.join(ts.split('_')[5:8]) + ' ' + ':'.join(ts.split('_')[8:])
            ts_record = ts_start + ',' + ts_end

            # 若未上传，则保存至MySQL
            if ts_record not in ts_list:
                db.upload_ids(sql_base=QUERY_SQL_INSERT, ids=ids, ts_start=ts_start, ts_end=ts_end)

            # 记录已上传的时间段
            with open('ts_upload', 'a') as f:
                f.write(str(idx) + ': ' + ts_record + '\n')
