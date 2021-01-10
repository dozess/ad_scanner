from os import mkdir, remove, listdir
from os.path import isdir, isfile, join
from datetime import datetime
import time
import random

from celery import Celery

from urllib.request import urlretrieve, urlopen, Request

from selenium import webdriver
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

import pymongo
from bson.objectid import ObjectId

import cv2
import pyzbar.pyzbar as pyzbar
from PIL import Image as im


import subprocess


# configuration
# TODO: Set configuration ouside script
CONF_MONGODB = "mongodb://192.168.1.200:27017/"
CONF_MDB_COLECTION = "skelbimai"
CONF_IMAGE_PATH = '/mnt/ad_keeper/image_archyve/'
CONF_MIN_DELAY = 10
CONF_MAX_DELAY = 20
CONF_INSCRIPT_VPN = True
CONF_PROFILES_VPN = '/mnt/ad_keeper/euvpn/'
CONF_AUTH_VPN = '/mnt/ad_keeper/pass.txt'
conf_path = '/mnt/ad_keeper/test_udp.ovpn'
auth_path = '/mnt/ad_keeper/vpn/pass.txt'


#setup celery
app = Celery('tasks', broker='pyamqp://saulius:saga93@192.168.1.21//')

#test function
@app.task
def add(x, y):
    return x + y

def create_folder(path):

    if not isdir(path):
        try:
            mkdir(path)
            return True
        except OSError:
            print ("Creation of the directory {} failed".format(path))
            return False
    else:
        return True

def download_ad(new_ad):
    print('Start procedure')
    #open VPN conection
    sISO = ''
    if CONF_INSCRIPT_VPN:
        vpn_conected = False
        while not vpn_conected:
            # get all possible VPN profiles
            vpn_profiles = [f for f in listdir(CONF_PROFILES_VPN) if isfile(join(CONF_PROFILES_VPN, f))]
            vpn_profile = random.choice(vpn_profiles)
            print('Try '+vpn_profile)
            sISO = vpn_profile[0:2]
            vpn_profile = join(CONF_PROFILES_VPN, vpn_profile)
            #start VPN process
            x = subprocess.Popen(['sudo', 'openvpn',
                                  '--config', vpn_profile,
                                  '--user', 'pi',
                                  '--auth-user-pass', CONF_AUTH_VPN], stdout=subprocess.PIPE)
            # wait until conection is established timeout 60s
            counter = 0 
            while True:
                time.sleep(1)
                counter += 1
                vpn_output = str(x.stdout.readline())

                print(vpn_output)
                if 'Initialization Sequence Completed' in vpn_output:
                    vpn_conected = True
                    print('VPN OK')
                    break
                if counter == 60 or 'TLS Error' in vpn_output:
                    break

            # if conection was not established - kill open vpn and start over
            if not vpn_conected:
                print('Reseting VPN')
                k = subprocess.Popen(['sudo', 'killall', 'openvpn'])

                # wait while VPN process is terminated
                while x.poll() != 0:
                    time.sleep(1)

                k = None



    sIP = urlopen('https://api.ipify.org/').read().decode()
    print (sISO +  ': ' + sIP)

    # if parsed successfully new status will be set to 'complete'
    new_ad['status'] = 'complete'

    # if not base_url in new_ad['url']:
    #     new_ad['url'] = base_url + new_ad['url']

    # setup chrome browser
    options = Options()
    options.add_argument('window-size=1100,1200')
    driver = webdriver.Chrome(options=options)

    # browse ad
    driver.get(new_ad['url'])

    soup = BeautifulSoup(driver.page_source, "html.parser")

    recapcha = soup.find('div', attrs={'id': 'validation-form'})

    # reCapcha : jei radom - stabdom darba
    if recapcha != None:
        driver.quit()
        return {'status': 'terminate'}

    # path from archyve folder without filename
    path = new_ad['ad_category']
    create_folder(join(CONF_IMAGE_PATH, path))

    # jeigu blokuotas pazymim istrinimui
    disabled = soup.find('div', attrs={'id': 'notFoundAdsArea'})
    if disabled != None:
        print('1. Skelbimas ', new_ad['url'], ' blokuotas. Pažymime ištrynimui')
        new_ad['status'] = 'remove'
        driver.quit()
        return new_ad

    # skelbimo screenshotas - jeigu skelbimas uzdarytas, parduotas ar dar kas ji pazymim istrinimui
    try:
        # jeigu random 'disabled info container' vadinasi skelbimo nebera
        disabled = driver.find_element_by_class_name('disabled-info-container')
        print('2. Neaktyvus: '+new_ad['url'])
        new_ad['status'] = 'remove'
        driver.quit()
        return new_ad
    except:
        # jeigu bandant rasti 'disabled info container' kilo klaida vadinasi skelbimas vis dar aktyvus
        pass

    # paslepiam telefono numerį iš screenshoto jeigu jis yra
    try:
        phone = driver.find_element_by_xpath(
            "//div[@class='contact-buttons']/div[@class='phone-button']/div[@class='primary']")
        is_phone = True
        driver.execute_script("arguments[0].setAttribute('style','display:none;');", phone)
    except:
        is_phone = False

    # paskrolinam puslapi kad nesimatytu reklamu headerio
    element = driver.find_element_by_id('contentArea')
    element.location_once_scrolled_into_view
    screenshot_name = join(path, 'screenshot_' + new_ad['site_id'] + '.png')
    driver.save_screenshot(join(CONF_IMAGE_PATH, screenshot_name))
    new_ad['screenshot'] = screenshot_name

    # atstatome telefono numeri
    if is_phone:
        driver.execute_script("arguments[0].setAttribute('style','display:visible;');", phone)

    # nukraunam skelbimo nuotraukas
    ad_images = []

    thumbs = driver.find_elements_by_class_name('js-open-photo')
    if len(thumbs) <= 0:
        print('3. Skelbimas ', new_ad['url'], ' neturi nuotraukų. Pažymime ištrynimui')
        new_ad['status'] = 'remove'
        driver.quit()
        return new_ad

    thumbs[0].location_once_scrolled_into_view
    thumbs[0].click()
    time.sleep(1)

    # imgs = driver.find_elements_by_class_name('pswp__img')
    imgs = driver.find_elements_by_xpath("//div[@class='pswp__zoom-wrap']/img[@class='pswp__img']")
    # print(imgs)

    if imgs == None:
        print('4. Skelbimas ', new_ad['url'], ' neturi nuotraukų. Pažymime ištrynimui')
        new_ad['status'] = 'remove'
        driver.quit()
        return new_ad

    driver.find_element_by_tag_name('body').send_keys(Keys.ESCAPE)

    img_urls = [img.get_attribute('src') for img in imgs]
    # print(img_urls)

    if img_urls == None:
        print('5. Skelbimas ', new_ad['url'], ' neturi nuotraukų. Pažymime ištrynimui')
        new_ad['status'] = 'remove'
        driver.quit()
        return new_ad

    for img_url in img_urls:

        filename = join(path, new_ad['site_id'] + ' ' + img_url.split('/')[-2] + '_' + img_url.split('/')[
            -1])  # '{}{}\{}_{}_{}'.format(image_library, new_ad['site_id'],img_url.split('/')[-2],img_url.split('/')[-1])

        if not isfile(join(CONF_IMAGE_PATH, filename)):
            urlretrieve(img_url, join(CONF_IMAGE_PATH, filename))
        ad_images += [
            {'site_id': new_ad['site_id'], 'external_url': img_url, 'local_file': filename, 'created': datetime.now(),
             'modified': datetime.now()}]
    new_ad['photos'] = ad_images.copy()
    new_ad['barcode'] = 'new'
    # x=mydb.image_archyve.insert_many(ad_images)

    # visa kita skelbimo txt info

    # mydb.skelbimai.update_one({'_id':new_ad['_id']},{'$set':new_ad})

    data_fields = []
    data_fields.append({'name': 'title', 'get': ('h1', {'itemprop': 'name'})})
    data_fields.append({'name': 'cities', 'get': ('p', {'class': 'cities'})})
    data_fields.append({'name': 'ad_text', 'get': ('div', {'class': 'description'})})
    data_fields.append({'name': 'contact', 'get': ('div', {'class': 'primary'})})

    # nukraunam skelbimo textine informacija

    for field in data_fields:
        element = soup.find(field['get'][0], field['get'][1])
        if element != None:
            new_ad[field['name']] = element.text.strip()

    # nukraunam kategoriju medi
    tags = [item.text.lower() for item in
            driver.find_element_by_class_name('category-path').find_elements_by_xpath("//span[@itemprop='title']")]
    new_ad['tags'] = tags

    # close chrome browser
    driver.quit()

    # send terminate signal to VPN process
    if CONF_INSCRIPT_VPN:
        k = subprocess.Popen(['sudo', 'killall', 'openvpn'])

        # wait while VPN process is terminated
        while x.poll() != 0:
            vpn_output = str(x.stdout.readline())

            print(vpn_output)

            time.sleep(1)

        k = None
    
    return new_ad

@app.task
def get_barcodes(db_id):

    dbclient = pymongo.MongoClient(CONF_MONGODB)
    db = dbclient[CONF_MDB_COLECTION]

    doc = db.skelbimai.find_one({'_id': ObjectId(db_id)})
    doc['status'] = 'complete'
    barcodes = []
    for photo in doc['photos']:
        file_name = join(CONF_IMAGE_PATH, photo['local_file'])
        if isfile(file_name):
            # original_image = im.open(file_name)
            original_image = cv2.imread(file_name, cv2.COLOR_RGB2GRAY)
            blur = cv2.GaussianBlur(original_image, (5, 5), 0)
            ret, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            objects = pyzbar.decode(th)
            if objects:
                photo['barcode'] = []
                for obj in objects:
                    photo['barcode'].append(obj.data.decode())
        if 'barcode' in photo.keys():
            barcodes = barcodes + photo['barcode']
    if barcodes:
        doc['barcodes'] = barcodes
    db.skelbimai.update_one({'_id': doc['_id']}, {'$set': doc})
    print(db_id + " : " + str(len(barcodes)) + " : OK")

@app.task
def delete_by_id(id):

    #create connection to mongodb
    try:
        myclient = pymongo.MongoClient(CONF_MONGODB)
        mydb = myclient[CONF_MDB_COLECTION]
    except:
        print('No data base connection')

    # load record to be deleted
    try:
        ad_to_remove = mydb.skelbimai.find_one({'_id': ObjectId(id)})
    except:
        print('Record not found.')

    # delete files of ad  -  photos
    if 'photos' in ad_to_remove:
        for img in ad_to_remove['photos']:
            try:
                file_name = join(CONF_IMAGE_PATH, img['local_file'])
                remove(file_name)
                print(id + ' : Removed ' + file_name)
            except:
                print(id + ' : PHOTO NOT FOUND ' + img['local_file'])

    # delete files of ad  -  screenshot
    if 'screenshot' in ad_to_remove:
        try:
            file_name = join(CONF_IMAGE_PATH, ad_to_remove['screenshot'])
            remove(file_name)
            print(id + ' : Removed ' + file_name)
        except:
            print(id + ' : SCREENSHOT NOT FOUND ' + file_name)

    # delete record from database
    try:
        mydb.skelbimai.delete_one(ad_to_remove)
        print(id + ' : Removed')
        return (True)
    except:
        print(id + ' : RECORD NOT FOUND')
        return (False)

@app.task
def get_ad_by_id(id):

    timeDelay = random.randrange(CONF_MIN_DELAY, CONF_MAX_DELAY)
    #    sleeppbar.reset(total=timeDelay)
    for i in range(timeDelay):  # , desc='Sleep for {} seconds'.format( timeDelay)):
        #        sleeppbar.update()
        time.sleep(1)

    # load db record of target ad
    try:
        myclient = pymongo.MongoClient(CONF_MONGODB)
        mydb = myclient[CONF_MDB_COLECTION]
    except:
        print('No mongo data base connection')

    try:
        ad = mydb.skelbimai.find_one({'_id': ObjectId(id)})
    except:
        print('Record not found.')

    # Set values for modified and status update for working on record
    ad['modified'] = datetime.now()

    if ad['status'] == 'selected':
        ad['status'] = 'remove'
    if ad['status'] == 'new':
        ad['status'] = 'selected'

    mydb.skelbimai.update_one({'_id': ad['_id']}, {'$set': ad})

    try:
        ad = download_ad(ad.copy())
    except UnexpectedAlertPresentException:
        print('Recapcha alert detected')
        return
    # display(ad)
    if ad['status'] == 'terminate':
        return
    elif ad['status'] == 'remove':
        delete_by_id.apply_async(args=[str(ad['_id'])], kwargs={})
    else:
        mydb.skelbimai.update_one({'_id': ad['_id']}, {'$set': ad})
        get_barcodes.apply_async(args=[str(ad['_id'])], kwargs={})
