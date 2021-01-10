from celery import Celery


CONF_MONGODB = 'mongodb://192.168.1.200:27017/'
CONF_MDB_COLECTION = 'skelbimai'
CONF_IMAGE_PATH = '/mnt/ad_keeper/'
CONF_MIN_DELAY = 10
CONF_MAX_DELAY = 20

app = Celery('tasks', broker='pyamqp://saulius:saga93@192.168.1.21//')

@app.task
def add(x, y):
    return x + y

@app.task
def delete_by_id(id):
    import pymongo
    from bson.objectid import ObjectId
    import os
    try:
        myclient = pymongo.MongoClient(CONF_MONGODB)
        mydb = myclient[CONF_MDB_COLECTION]
    except:
        print('No data base connection')
        
    try:
        ad_to_remove = mydb.skelbimai.find_one({'_id':ObjectId(id)})
    except:
        print('Record not found.')
        
    if 'photos' in ad_to_remove:
        for img in ad_to_remove['photos']:

            try:
                file_name = os.path.join(CONF_IMAGE_PATH, img['local_file'])
                os.remove(file_name)
                print(id+' : Removed ' + file_name)
            except:
                print(id + ' : PHOTO NOT FOUND '+ img['local_file'])
    if 'screenshot' in ad_to_remove:
        try:
            file_name = os.path.join(CONF_IMAGE_PATH, ad_to_remove['screenshot'])
            os.remove(file_name)
            print(id + ' : Removed ' + file_name)
        except:
            print(id + ' : SCREENSHOT NOT FOUND '+ file_name)
    try:
        mydb.skelbimai.delete_one(ad_to_remove)
        print(id + ' : Removed')
        return(True)
    except:
        print(id + ' : RECORD NOT FOUND')
        return(False)


@app.task
def get_barcodes(db_id):
    import pymongo
    import pyzbar.pyzbar as pyzbar
    from PIL import Image as im
    from os.path import isfile, join
    from bson.objectid import ObjectId

    dbclient = pymongo.MongoClient(CONF_MONGODB)
    db = dbclient[CONF_MDB_COLECTION]

    doc=db.skelbimai.find_one({ '_id':ObjectId(db_id)})
    doc['status']='complete'
    barcodes = []
    if 'photos' in doc.keys():
        for photo in doc['photos']:
            file_name = join(CONF_IMAGE_PATH, photo['local_file'])
            if isfile(file_name):
                print('file : ' + file_name)
                original_image = im.open(file_name)
                objects = pyzbar.decode(original_image)
                if objects:
                    photo['barcode']=[]
                    for obj in objects:
                        photo['barcode'].append(obj.data.decode())
            if 'barcode' in photo.keys():
                barcodes = barcodes + photo['barcode']
    if barcodes:
        doc['barcodes']=barcodes
    db.skelbimai.update_one({'_id':doc['_id']},{'$set':doc})
    print(db_id + " : " +str(len(barcodes)) + " : OK")
