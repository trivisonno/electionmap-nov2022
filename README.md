This election map app runs virtually in AWS Lambda, written in Python and deployed using Zappa. The map runs on LeafletJS.

You'll need an S3 bucket to host two files (nov2022_precincts.geojson and 2014wardboundaries.geojson) and the turnout JSON file that the python app generates every minute. Mine is 'cuyahogavoters', so you'll need to change this to the name of your S3 bucket. You'll also need to allow for bucket read (make your bucket files public).

The zappa_settings.json file includes an expression to run the python function every minute. Every election you'll need to update the CSV file URL on L33 of app.py.

This repo doesn't include everything I use for this project, but is the bare minimum to get you started at least with the real-time Leaflet map.
