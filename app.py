# pip install requests boto3 flask
import json
import csv
import requests
import time
import urllib3
import boto3
import os
from flask import Flask
from datetime import datetime
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
s3 = boto3.client('s3')
app = Flask(__name__)

def getTurnout():
    date_time = datetime.now().strftime("%m%d%YT%H%M%S")

    if os.path.exists('/tmp/nov2022_precincts.geojson') == False:
        s3.download_file('cuyahogavoters', 'nov2022_precincts.geojson', '/tmp/nov2022_precincts.geojson')
    with open("/tmp/nov2022_precincts.geojson", "r") as f:
        geojson_data = json.load(f)



    updatedGeojson = {"type":"FeatureCollection","features":[]}

    #response = requests.get("https://www.livevoterturnout.com/cuyahoga-nov-03-2020/TurnoutByPrecinctTable.csv", verify=False)
    #response = requests.get("https://www.livevoterturnout.com/Cuyahoga-sep-14-2021/TurnoutByPrecinctTable.csv", verify=False)
    # response = requests.get("https://www.livevoterturnout.com/Cuyahoga-nov-02-2021/TurnoutByPrecinctTable.csv", verify=False)
    # Nov 8, 2022, https://www.livevoterturnout.com/cuyoh/LiveResults/en/Index_19.html
    response = requests.get("https://updates.electionlink.net/widgets/cuyoh/2022-11-08/TurnoutByPrecinctTable.csv", verify=False)
    with open("/tmp/turnout-"+date_time+".csv","wb") as f:
         f.write(response.content)

    newvoterdata = []
    latestTime = ''
    with open("/tmp/turnout-"+date_time+".csv","r") as f:
        csv_reader = csv.DictReader(f)

        line_count = 0
        for row in f.readlines():
            if line_count == 0:
                latestTime = row.split('    ')[1].strip()
            if line_count > 1:
                precinct = row.split(',')[0].replace(" -","-")
                totalregistered = row.split(',')[1]
                absentee = row.split(',')[2]
                inperson = row.split(',')[3]
                newvoterdata.append([precinct, [totalregistered, absentee,  inperson]])
            line_count += 1

    v2json = {'lastUpdated': latestTime}
    largestValue = 0
    maxRemaining = 0
    for feature in geojson_data["features"]:
        for line in newvoterdata:
            if line[0] == feature["properties"]["Name"]:
                turnout = round((int(line[1][1])+int(line[1][2]))/(int(line[1][0]))*100,1)
                votesUnaccounted = (int(line[1][0])) - (int(line[1][1])+int(line[1][2]))
                updatedGeojson["features"].append({"type":"Feature", "geometry":feature['geometry'],"properties":{"updated": latestTime,"name":feature["properties"]["Name"],"turnoutPct":turnout, "totalRegistered":line[1][0],"absentee":line[1][1],"inPerson":line[1][2], "votesUnaccounted":votesUnaccounted, "pollingLocation":feature["properties"]["Location"], "pollingLocationAdd":feature["properties"]["Address"]}})

                v2json[feature["properties"]["Name"]] = {}
                v2json[feature["properties"]["Name"]]["turnout"] = turnout
                v2json[feature["properties"]["Name"]]["reg"] = int(line[1][0])
                v2json[feature["properties"]["Name"]]["abs"] = int(line[1][1])
                v2json[feature["properties"]["Name"]]["inPerson"] = int(line[1][2])
                v2json[feature["properties"]["Name"]]["novote"] = votesUnaccounted
                if (votesUnaccounted > maxRemaining): maxRemaining = votesUnaccounted
                if (int(line[1][1])+int(line[1][2]) > largestValue): largestValue = int(line[1][2])+int(line[1][1])
    v2json['maxValue'] = largestValue
    v2json['maxRemaining'] = maxRemaining


    updatedGeojsonTotalVotes = {"type":"FeatureCollection","features":[]}
    for feature in geojson_data["features"]:
        for line in newvoterdata:
            if line[0] == feature["properties"]["Name"]:
                votes = int(line[1][1])+int(line[1][2])
                updatedGeojsonTotalVotes["features"].append({"type":"Feature", "geometry":feature['geometry'],"properties":{"updated": latestTime,"name":feature["properties"]["Name"],"votes":votes, "pollingLocation":feature["properties"]["Location"], "pollingLocationAdd":feature["properties"]["Address"]}})



    polls = {}
    for feature in updatedGeojson['features']:
        if feature['properties']['name'][0:10] == "CLEVELAND-":
            if feature['properties']['pollingLocation']=="Brooklyn Heights United Church of Christ":
                feature['properties']['pollingLocation'] = 'BROOKLYN HTS UNITED CHURCH OF CHRIST'
            if feature['properties']['pollingLocation']=="FATIMA FAMITY CENTER":
                feature['properties']['pollingLocation'] = 'FATIMA FAMILY CENTER'

            try:
                polls[feature['properties']['pollingLocation']]['inPerson'] = int(polls[feature['properties']['pollingLocation']]['inPerson']) + int(feature['properties']['inPerson'])
            except:
                polls[feature['properties']['pollingLocation']] = {}
                polls[feature['properties']['pollingLocation']]['inPerson'] = int(feature['properties']['inPerson'])
                polls[feature['properties']['pollingLocation']]['pollingLocationAdd'] = feature['properties']['pollingLocationAdd']
                polls[feature['properties']['pollingLocation']]['ward'] = feature['properties']['name'].split('-')[0] + '-' + feature['properties']['name'].split('-')[1]

    pollList = []
    for k, v in polls.items():
        pollList.append([v['inPerson'], k, v['pollingLocationAdd'], v['ward']])

    def sortSecond(val):
        return val[0]

    pollList.sort(key=sortSecond, reverse=True)

    if os.path.exists('/tmp/2014wardboundaries.geojson') == False:
        s3.download_file('cuyahogavoters', '2014wardboundaries.geojson', '/tmp/2014wardboundaries.geojson')
    with open("/tmp/2014wardboundaries.geojson", "r") as f:
        wards = json.load(f)


    clevelandWardDict = {}
    v2jsonCopy = {}

    for k, v in v2json.items():
        if k[0:10] == "CLEVELAND-":
            wardName = 'WARD-'+k[0:12]
            v2jsonCopy[k] = v
            v2jsonCopy[wardName] = {"turnout": 0, "reg": 0, "abs": 0, "inPerson": 0, "novote": 0}
        else:
            v2jsonCopy[k] = v

    v2json = v2jsonCopy

    largestValueWard = 0
    maxRemainingWard = 0

    wardVotesGeojson = {"type": "FeatureCollection", "features": []}
    for ward in wards["features"]:


        for k, v in v2json.items():
            if k[0:10] == "CLEVELAND-":
                if 'WARD-'+k[0:12] == 'WARD-CLEVELAND-'+str(ward['properties']['ward']).zfill(2):
                    #print(k,v)
                    v2json['WARD-'+k[0:12]]["reg"] += v["reg"]
                    v2json['WARD-'+k[0:12]]["abs"] += v['abs']
                    v2json['WARD-'+k[0:12]]["inPerson"] += v['inPerson']
                    v2json['WARD-'+k[0:12]]["novote"] += v['reg']-v['abs']-v['inPerson']

                    v2json['WARD-'+k[0:12]]["turnout"] = round(((v2json['WARD-'+k[0:12]]["abs"]+v2json['WARD-'+k[0:12]]["inPerson"])/v2json['WARD-'+k[0:12]]["reg"])*100, 1)
                    if (v2json['WARD-'+k[0:12]]["novote"] > maxRemainingWard): maxRemainingWard = v2json['WARD-'+k[0:12]]["novote"]
                    if (v2json['WARD-'+k[0:12]]["abs"]+v2json['WARD-'+k[0:12]]["inPerson"] > largestValueWard): largestValueWard = v2json['WARD-'+k[0:12]]["inPerson"]+v2json['WARD-'+k[0:12]]["abs"]
    v2json['maxValueWard'] = largestValueWard
    v2json['maxRemainingWard'] = maxRemainingWard


    with open('/tmp/turnout.json', 'w') as f:
        f.write(json.dumps(v2json))

    s3.upload_file(
        Filename='/tmp/turnout.json',
        Bucket='cuyahogavoters',
        Key='turnout.json',
        ExtraArgs={
            "ContentType": "application/json"
        }
    )

    s3.upload_file(
        Filename='/tmp/turnout.json',
        Bucket='cuyahogavoters',
        Key='data/turnout-'+date_time+'.json',
        ExtraArgs={
            "ContentType": "application/json"
        }
    )

    with open('/tmp/polls.json', 'w') as f:
        f.write(json.dumps(pollList))

    s3.upload_file(
        Filename='/tmp/polls.json',
        Bucket='cuyahogavoters',
        Key='data/polls-'+date_time+'.json',
        ExtraArgs={
            "ContentType": "application/json"
        }
    )

    s3.upload_file(
        Filename='/tmp/polls.json',
        Bucket='cuyahogavoters',
        Key='polls.json',
        ExtraArgs={
            "ContentType": "application/json"
        }
    )


if __name__ == "__main__":
    getTurnout()
