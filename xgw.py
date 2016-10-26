#!/usr/bin/env python

import os
import sys
import time
import socket
import json
import threading
import ConfigParser
import fcntl, struct
import traceback
import logging
import filecmp
from logging.handlers import RotatingFileHandler

dirname, filename = os.path.split(os.path.abspath(sys.argv[0]))
header=["virtual_server","local_address_"]

class Comparison:
    def __init__(self):
        self.type="Xgw-diff"
        self.dirpath=dirname
        self.current_path=dirname
        self._init_log()
        self.conf=self.load_conf()

    def _init_log(self):
        self.LOG = logging.getLogger(self.type)
        handler = RotatingFileHandler(os.path.join(self.dirpath, '%s.log' % self.type),maxBytes=1024*1024*50,backupCount=5)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(filename)s - %(message)s'))
        self.LOG.addHandler(handler)
        self.LOG.setLevel(logging.INFO)

    def load_conf(self):
        try:
            cfg = ConfigParser.ConfigParser()
            cfg.read(os.path.join(self.dirpath, 'conf.ini'))
            conf_dict = {}
            for section in cfg.sections():
                conf_dict[section] = {}
                for k, v in cfg.items(section):
                    conf_dict[section][k] = v
            return conf_dict["common"]
        except Exception as e:
            self.LOG.error('Load conf Exception:%s' % e)
            raise e

    def get_file_from_scp(self,private_key,name,IP,sourcefile,targetfile):
        try:
            cmd="scp -i "+private_key+" "+name+"@"+IP+":"+sourcefile+" "+targetfile
            os.popen(cmd)
        except Exception as e:
            self.LOG.info("error when scp from %s,the exception is %s" % IP % e)

    def get_config(self):
        try:
            IPs=self.conf["ip"].split('|')
            timestr=time.strftime("%Y%m%d")
            self.current_path=os.path.join(self.dirpath,timestr)
            os.mkdir(self.current_path)
            for ip in IPs:
                filepath=os.path.join(self.current_path,ip)
                self.get_file_from_scp(self.conf["private_key"],"root",ip,self.conf["sourcefile"],filepath)
        except Exception as e:
            traceback.print_exc()
            self.LOG.info("the error position is get_config(),error mes is %s" % e)
        return dirpath,IPs
    
    def get_errorlog(self):
        pass

    def CmpConf(self,dirpath,filenames):
        list_set=[]
        list_set.append(set())
        list_set[0].add(filenames[0])
        for filename in filenames:
            file_path=os.path.join(dirpath,filename)
            isdiff=0
            for item in list_set:
                first=item.pop()
                key_path=os.path.join(dirpath,first)
                if filecmp.cmp(file_path,key_path):
                    item.add(filename)
                    item.add(first)
                    isdiff=1
                    break;
                else:
                    item.add(first)
            if isdiff==0:
                s=set()
                s.add(filename)
                list_set.append(s)
        return list_set

    def get_single_block(self,i,s):
        block=""
        num=0
        first=0
        for j in range(i,len(s)):
            block=block+s[j]
            if s[j]=='{':
                if first==0:
                    first=1
                num=num+1
            if s[j]=='}':
                num=num-1
            if num==0 and first==1:
                block=block+'\n'
                return j,block

    def get_all_block(self,s):
        blocks=[]
        for i in range(len(s)):
            if s[i:i+14] in header:
                j,block=self.get_single_block(i,s)
                i=j
                blocks.append(block)
        return blocks

    def Union(self,blocks,string):
        b1=self.get_all_block(string)
        c12=[i for i in blocks if i in b1]
        c21=[i for i in b1 if i in blocks]
        if len(c12)>len(c21):
            return c21
        else:
            return c12

    #l is the list of set
    def Union_all(self,l):
        first=l[0].pop()
        l[0].add(first)
        file1path=os.path.join(self.current_path,first)
        file1=open(file1path)
        s1=file1.read()
        b1=self.get_all_block(s1)
        for i in range(len(l)):
            second=l[i].pop()
            l[i].add(second)
            file2path=os.path.join(self.current_path,second)
            file2=open(file2path)
            s2=file2.read()
            same=self.Union(b1,s2)
            b1=same
        return same

    def work(self):
        #dirpath,IPs=self.get_config()
        dirpath="/mnt/share"
        IPs=[]
        for i in range(20):
            temp="test"+str(i)
            IPs.append(temp)

        l=self.CmpConf(dirpath,IPs)
        index=0
        maxlength=-1
        for i in range(len(l)):
            length=len(l[i])
            if length>maxlength:
                maxlength=length
                index=i
        if len(l)==1:
            self.LOG.info("this day is Normal")
            print "OK"
            return 1

        self.LOG.info(l)
        same=self.Union_all(l)
        temp_path=os.path.join(self.current_path,"same")
        f=open(temp_path,"w")
        f.writelines(same)
        f.close()

        for i in range(len(l)):
            first=l[i].pop()
            l[i].add(first)
            path=os.path.join(self.current_path,first)
            f=open(path)
            s=f.read()
            b=self.get_all_block(s)
            diff=[j for j in b if j not in same]
            if len(diff)!=0:
                diff_filaname="the_difference_of_"+str(i)+"_set"
                path=os.path.join(self.current_path,diff_filaname)
                tempf=open(path,"w")
                tempf.writelines(diff)
        
    def send_message(self,fromaddress,toaddress,content):
        msg=MTMEText(content,'plain','utf-8')
        msg['Subject']="error"+time.strftime("%Y%m%d")
        msg['From']=fromaddress
        msg['To']=";".join(toaddress)
        try:
            server=smtplib.SMTP()
            server.connect(self.conf["mail_host"])
            server.login(self.conf["mail_user"],self.conf["mail_pass"])
            server.aendmail(fromaddress,toaddress,msg.as_string())
            server.close()
        except Exception as e:
            self.LOG.info("it has an error when send message,the error is % s" % e)

if __name__== '__main__':
    xgw=Comparison()
    xgw.work()
    
