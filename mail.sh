#!/usr/bin/env bash
# 记录开始时间
echo `date` >> /Users/zhoujl/workspace/netease/auto/log &&

# 切换至工作目录
cd /Users/zhoujl/workspace/netease/auto &&

# 执行python脚本
/anaconda3/envs/tensorflow/bin/python mail.py &&

# 运行完成
echo 'finish' >> /Users/zhoujl/workspace/netease/auto/log

