import urllib2, re, sqlite3, hashlib
from time import sleep
import xml.etree.ElementTree as ET

class FEDB(object):
    def __init__(self):
        # Setup URLs for gathering data from fueleconomy.gov
        self.base_url   = "http://fueleconomy.gov/ws/rest"
        self.year_ext   = "/vehicle/menu/year"
        self.makes_ext  = "/vehicle/menu/make?year=%s"
        self.mod_ext    = "/vehicle/menu/model?year=%s&make=%s"
        self.mod_opt_ext= "/vehicle/menu/options?year=%s&make=%s&model=%s"
        self.usr_veh_ext= "/ympg/shared/ympgVehicle/%s"
        self.man_veh_ext= "/vehicle/%s"

        # Initialize SQL DB
        self.sql = sqlite3.connect("fuelecon.db")
        self.cur = self.sql.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS vehicle_data(id TEXT, year INTEGER, make TEXT, model TEXT, desc TEXT, avg_mpg REAL)")
        self.sql.commit()

    def fetch_data_list(self, url_ext):
        val_list = []
        for val in ET.fromstring(urllib2.urlopen(self.base_url + url_ext).read()):
            val_list.append(val[0].text)
        return val_list

    # Reported user data > manufacturers data
    def calc_fuel_econ(self, opt_id):
        veh_data = ET.fromstring(urllib2.urlopen((self.base_url + self.man_veh_ext) % opt_id).read())
        has_mpg_data = veh_data.find("mpgData").text
        if has_mpg_data == "N":
            mpg = (float(veh_data.find("comb08U").text) + float(veh_data.find("combA08U").text)) / 2
        elif has_mpg_data == "Y":
            mpg = float(ET.fromstring(urllib2.urlopen((self.base_url + self.usr_veh_ext) % opt_id).read())[0].text)
        return mpg
        
    def update_db(self):
        # Gather a list of all model years available
        for year in self.fetch_data_list(self.year_ext):
            print "[*] Getting data for year: %s..." % year,
            # Gather makes in the year
            for make in self.fetch_data_list(self.makes_ext % year):
                make_url_fmt = make.replace(" ", "%20")                     #<-- Format the make for use in the url
                # Gather models for the make in the year
                for model in self.fetch_data_list(self.mod_ext % (year, make_url_fmt)):
                    mod_url_fmt = model.replace(" ", "%20")                 #<-- Format the model for use in the url
                    # Gather options for model
                    for opt in ET.fromstring(urllib2.urlopen((self.base_url + self.mod_opt_ext) % (year, make_url_fmt, mod_url_fmt)).read()):
                        option = opt[0].text                                #<-- Get the actual text for the option
                        opt_id = opt[1].text
                        avg_mpg = self.calc_fuel_econ(opt_id)
                        u_string = year + make + model + option
                        u_hash = hashlib.md5(u_string).hexdigest()[:15]     #<-- Generate unique hash based on make, model, and option
                        self.cur.execute("SELECT * FROM vehicle_data WHERE id=?", (u_hash,))
                        result = self.cur.fetchone()
                        if not result:
                            self.cur.execute("INSERT INTO vehicle_data VALUES(?,?,?,?,?,?)", (u_hash, int(year), make, model, option, avg_mpg))
                        elif result[5] != avg_mpg:
                            self.cur.execute("UPDATE vehicle_data SET avg_mpg=? WHERE id=?", (avg_mpg, u_hash))
                        self.sql.commit()
            print "DONE"
            sleep(5)