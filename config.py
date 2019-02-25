#!/usr/bin/python
# -*- coding:utf-8 -*-
################################################################################
#
# Copyright (c) 2019 ***.com, Inc. All Rights Reserved
# Copyright 2019, The NSH Anti-Plugin Project
################################################################################
"""
NSH脚本异常用户ID -- 邮件读取和存储MySQL
使用MacOS的定时工具Launchctl，每天定时读取包含指定关键词的邮件，解析内容，并上传结果至MySQL

Usage: 配置跳板服务器、MySQL以及邮箱参数
Authors: Zhou Jialiang
Email: zjl_sempre@163.com
Date: 2019/02/18
"""

# Remote Server Config
LOCAL_HOST = '127.0.0.1'
SSH_HOST = '***.***.***.***'
SSH_PORT = 32200
SSH_PKEY = '/Users/zhoujl/.ssh/id_rsa_***'
SSH_USER = '***'
SSH_PASSWORD = ''

# MySQL Config
MYSQL_HOST = '***.***.***.***'
MYSQL_PORT = 3306
MYSQL_USER = '***'
MYSQL_PASSWORD = '***'
MYSQL_DB = 'anti_plugin'

# 查询关键字
KEY_WORD_SUBJECT = '***'

# 账户密码
MAIL_ACCOUNT = '***'
MAIL_PASSWORD = '***'
IMAP_HOST = '***'
IMAP_PORT = 993
