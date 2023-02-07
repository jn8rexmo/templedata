from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from datetime import datetime
import json
import time
import mysql.connector
from mysql.connector import connect, Error

import logging
import logging.handlers
import os

from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_file_handler = logging.handlers.RotatingFileHandler(
    "status.log",
    maxBytes=1024 * 1024,
    backupCount=1,
    encoding="utf8",
)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger_file_handler.setFormatter(formatter)
logger.addHandler(logger_file_handler)


try:
    DB_HOST=os.environ["DB_HOST"]
    DB_USER=os.environ["DB_USER"]
    DB_PASSWORD=os.environ["DB_PASSWORD"]
    DB_DATABASE=os.environ["DB_DATABASE"]
    DB_PORT=os.environ["DB_PORT"]
    LDS_USER=os.environ["LDS_USER"]
    LDS_PASSWORD=os.environ["LDS_PASSWORD"]
except KeyError:
    logger.info("ENV variable(s) not available!")
# print(DB_PORT)
# if DB_PORT == '3307':
#     print("DB_PORT is as expected.")
# else:
#     print("DB_PORT is not as expected.")


if __name__ == "__main__":

    #--| Data set and variable initialization
    all_temples={}
    temple_data=[]
    temple_no_data=[]
    today=datetime.today().isoformat()[:10]
#     print(today)
    todaysdateID="#0/"+datetime.today().strftime('%d/%Y')
    todaysdateFile="./data/"+ datetime.today().strftime('%m-%d-%Y') +".txt"



    #--| Retrieve temple list from db
    try:
        with connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            port=DB_PORT
        ) as connection:
#             print(connection)
            select_temples_query = """
            SELECT temple_name, id FROM temples
            """

            with connection.cursor() as cursor:
                cursor.execute(select_temples_query)
                results=cursor.fetchall()
                for result in results:
                    all_temples[result[0]]=result[1]
#                 print("Temples found: ", all_temples)
    except Error as e:
#         print("error retrieving list of temples from db", e)
        logger.info("Error connecting to DB to retrieve list of temples")




    #--| Setup web driver
    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()))


    #--| Log In
    browser.get("https://id.churchofjesuschrist.org/")
    time.sleep(2)
    user_name = browser.find_element(By.CSS_SELECTOR,'#okta-signin-username')
    user_name.send_keys(LDS_USER)
    submit = browser.find_element(By.CSS_SELECTOR,'#okta-signin-submit')
    submit.click()
    time.sleep(5)

    password = browser.find_element(By.NAME,'password')
    password.send_keys(LDS_PASSWORD)
    submit = browser.find_element(By.CSS_SELECTOR,'.button-primary')
    submit.click()
    time.sleep(5)


    #--| Navigate to temples page
    browser.get("https://tos.churchofjesuschrist.org/?lang=eng")
    time.sleep(5)


    #--| Get list of available temples
    select_a_different_temple = browser.find_element(By.CSS_SELECTOR,'#select-a-different-temple-link')
    select_a_different_temple.click()
    time.sleep(2)
    temples=browser.find_elements(By.CSS_SELECTOR,'.temple-name-column>a')
    temple_names=[]
    for t in temples:
        temple_names.append(t.text)


    #--| Loop through list of temple names
    #Select tomorrow's date
    #Scrape either whole page or just the chunk of data
    #Select a date far in the future
    #Scrape its data to see the max #seats available

    for temple_name in temple_names:
        # Loop Data
        sessions=[]

        # Select temple
#         print(temple_name)
        t=browser.find_element(By.LINK_TEXT,temple_name)
        t.click()
        time.sleep(2)

        # Verify temple exists. if not, create it.
        if temple_name in all_temples.keys():
            t_id=all_temples[temple_name]
        else:
#             print("Temple not found: ", temple_name)
#             print("adding to db")
            try:
                with connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_DATABASE,
                    port=DB_PORT
                ) as connection:
#                     print(connection)
                    loc=browser.find_element(By.CSS_SELECTOR, '.your-temple-contact-info').text.replace("\n"," ")
                    add_temple_query = "INSERT INTO temples (temple_name, temple_location) VALUES ( \""+ temple_name + "\", \"" + loc + "\")"
#                     print(add_temple_query)

                    with connection.cursor() as cursor:
                        cursor.execute(add_temple_query)
                        connection.commit()
                        t_id=cursor.lastrowid
#                         print ("new id is ", t_id)
            except Error as e:
                logger.info("Error connecting to DB to insert new temple")
#                 print("error adding temple to db", e)
                
        





        # Click "select this temple"
        selectthis=browser.find_element(By.CSS_SELECTOR,"#select-this-temple-button")
        selectthis.click()
        time.sleep(5)

        # Click "Proxy Endowment"
        # endowment = browser.find_elements(By.XPATH, "//*[@id='appointment-type-selector']/div[2]/div/ordinance-selector/div/div[2]/div[3]/span/span[1]")
        endowment=browser.find_element(By.CSS_SELECTOR,"#appointment-type-selector > div.panel-collapse.collapse.in > div > ordinance-selector > div > div:nth-child(2) > div:nth-child(3) > span > span:nth-child(1)")
        endowment.click()
        time.sleep(2)

        # Select date of choice (This is currently disabled - it selects today by default.
        # opendatepicker=browser.find_element(By.CSS_SELECTOR,"#secondSelect")
        # opendatepicker.click()
        # try:
            # print(todaysdateID)
            # today=browser.find_element(By.CSS_SELECTOR,todaysdateID)
            # today.click()

        # Download page soup, extract the schedule
        soup = BeautifulSoup(browser.page_source, 'lxml')
        schedule_items = soup.find_all("div", {"class": "schedule-item"})

        # Iterate through the schedule, extracting data for each session
        for i in schedule_items[4:]:
            t=i.find("span", {"class": "schedule-item-text"}).text
            ty=i.find("span", {"class": "schedule-type"}).text
            s=i.find("span", {"class": "seats-available-message"}).text.replace(" Seats Available","")
            session=[today, t, s, ty, t_id]
#             print(session)
            sessions.append(session)

        # Store the data (or lack thereof)
        if sessions.count == 0:
            temple_no_data.append(temple_name)
        temple_data.append(sessions)

        # Write data to a JSON file (currently disabled)
        # with open(todaysdat
            # convert_file.write(json.dumps(temple_data))eFile, 'w') as convert_file:

        #--| Go back to temples page so the next can be selected
        browser.get("https://tos.churchofjesuschrist.org/?lang=eng")
        time.sleep(5)
        select_a_different_temple = browser.find_element(By.CSS_SELECTOR,'#select-a-different-temple-link')
        select_a_different_temple.click()
        time.sleep(2)


    #--| Send data to a JSON file (currently disabled)
    # todaysdateFile="./data/"+datetime.today().strftime('%M-%D-%Y')+".txt"
    # with open(todaysdateFile, 'a') as convert_file:
    #      convert_file.write(json.dumps(temple_data))


    #--| Insert data into DB
    try:
        with connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            port=DB_PORT
        ) as connection:
#             print(connection)
            insert_sessions_query = """
            INSERT INTO sessions
            (session_date, session_time, seats, session_type, temple_id)
            VALUES ( %s, %s, %s, %s, %s)
            """

            with connection.cursor() as cursor:
                cursor.executemany(insert_sessions_query, sessions)
                connection.commit()
    except Error as e:
        logger.info("Error connecting to DB to bulk insert data")
#         print("error inserting bulk data into db", e)




