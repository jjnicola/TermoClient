import sqlite3
from telnetlib import Telnet as tn
import time
import logging

class TermoComm():
    def __init__(self, logger):
        self.logger = logger

    def NewConn(self, host):
        self.logger.debug("new telnet connection")

        try:
            soc = tn(host)
            return soc
        except EOFError as er:
            self.logger.debug ("Error OS in TermoComm Class: {0}".format(err))

    def GetLog(self, soc):
        try:
            soc.write(("GTL:000%").encode('ascii'))
            dret = soc.read_until(b'S')
            return dret
        except EOFError as er:
            self.logger.debug ("Error OS in TermoComm Class: {0}".format(err))
            return False

    def SetDev(self, soc, profile):
        try:
            data = profile + '%'
            soc.write(data.encode('ascii'))
            time.sleep (10)
            return True
        except EOFError as er:
            self.logger.debug ("Error OS in TermoComm Class: {0}".format(err))
            return False

    def InitController(self, soc):
        try:
            soc.write(("0000000%").encode('ascii'))
            time.sleep (10)
            return True
        except EOFError as er:
            self.logger.debug ("Error OS in TermoComm Class: {0}".format(err))
            return False

    def CloseConn(self, soc):
        soc.close()


class TermoSql():
    def __init__(self, logger):
        self.logger = logger
    
    def NewDB(self):
        try:
            dbconn = sqlite3.connect('../Termoweb/termodb.sqlite3')
            self.logger.debug("new db: "+str(dbconn))
            return dbconn
        except sqlite3.Error as e:
            self.logger.debug ("Error OS in TermoSql Class:", e.args[0])

    def CloseDB(self,dbconn):
        dbconn.close()

    def Getbidfrombnumber(self, dbconn ,batch_number):
        '''Get the batch id from the db using the batch number'''
        try:
            c = dbconn.cursor()
            data = "select id from polls_batchinfo where batch_number = "+ str(batch_number)
            c.execute(data)
            return int(c.fetchone()[0])
        except sqlite3.Error as e:
            self.logger.debug ("Error OS in TermoSql Class:", e.args[0])

    def SaveData(self, dbconn, dret, batch_id):
        try:
            temp = float(dret[:-3])
            status = int(dret[5:6])
            taux = time.localtime()
            log_date = (str(taux.tm_year)+"-"+str(taux.tm_mon)+"-"+
                       str(taux.tm_mday)+" "+str(taux.tm_hour)+
                       ":"+str(taux.tm_min)+":"+str(taux.tm_sec))
            c = dbconn.cursor()
            data = "INSERT INTO polls_fermentationlog(log_date, density, dev_status, batch_id, temperature) VALUES ('" + log_date + "',1048," + str(status) + "," + str(batch_id) + "," + str(temp) + ")"
            c.execute(data)
            dbconn.commit()
        except sqlite3.Error as e:
            self.logger.debug ("Error OS in TermoSql Class:", e.args[0])


    def GetLastBatchNumber(self,dbconn):

        try:
            c = dbconn.cursor()
            data = "select batch_number from polls_batchinfo order by batch_number desc limit 1"
            c.execute(data)
            return int(c.fetchone()[0])
        except sqlite3.Error as e:
            self.logger.debug ("Error OS in TermoSql Class:", e.args[0])

    def CheckBatchNumber(self, dbconn, bnumber):
        if not dbconn:
            self.logger.debug("DB connection not initialized.")

        try:
            c = dbconn.cursor()
            data = "select batch_number from polls_batchinfo where batch_number = " +str(bnumber)
            c.execute(data)
            ret = c.fetchall()
            if not ret:
                return False
            else:
                return True
        except sqlite3.Error as e:
            self.logger.debug ("Error OS in TermoSql Class:", e.args[0])

    def CreateNewBatch (self, dbconn, name, bnumber, style):
        try:
            taux = time.localtime()
            log_date = str(taux.tm_year)+"-"+str(taux.tm_mon)+"-"+str(taux.tm_mday)+" "+str(taux.tm_hour)+":"+str(taux.tm_min)
            c = dbconn.cursor()
            data = "INSERT INTO polls_batchinfo (batch_number, batch_name, batch_style, batch_date) VALUES ("+str(bnumber)+",'"+name+"','"+style+"','"+log_date+"')"
            c.execute(data)
            dbconn.commit()
        except sqlite3.Error as e:
            self.logger.debug ("Error OS in TermoSql Class:", e.args[0])


