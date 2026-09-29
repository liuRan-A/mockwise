# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pymysql
c = pymysql.connect(host="127.0.0.1", user="root", password="3044544.Liu", database="mockwise")
cur = c.cursor()
cur.execute("select id,name,industry,position_type,form_type from question_sets")
print("== 套题 ==")
for r in cur.fetchall():
    print(r)
cur.execute("select id,set_id,category,dimension,seq,left(content,30),left(ref_answer,50) from questions order by set_id,seq limit 12")
print("== 题目 ==")
for r in cur.fetchall():
    print(r)
