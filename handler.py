import requests
import datetime
import os
import boto3
from dotenv import load_dotenv
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += 'DEFAULT:!DH'
cloudwatch = boto3.client('cloudwatch')
load_dotenv()
metrics = []

default_green_energy_threshold = 80
if os.getenv('GREEN_ENERGY_THRESHOLD'):
  try:
    green_energy_threshold = int(os.getenv('GREEN_ENERGY_THRESHOLD'))
    if green_energy_threshold < 0 or green_energy_threshold > 100:
      raise
  except:
    print("GREEN_ENERGY_THRESHOLD must be an integer between 0 and 100.  Default: 80")
    exit(1)
else:
  green_energy_threshold = default_green_energy_threshold

if os.getenv('SEQUEMATIC_URL_SUFFIX'):
  sequematic_url_suffix = os.getenv('SEQUEMATIC_URL_SUFFIX')
else:
  print("The environment variable SEQUEMATIC_URL_SUFFIX must be set.  Example: 9999/ABCDF0123/variable_name")
  exit(1)

fields = ['LblReadDate',
          'LblWindData',
          'LblHydroData',
          'LblThermData',
          'LblSolarData',
          'LblForecastData',
          'LblTotalData']

def add_metric(name, value):
  metrics.append(
      {
        'MetricName': name,
        'Dimensions': [{
          'Name': 'zone',
          'Value': 'US-MT-NWE'
        }],
        'Timestamp': datetime.datetime.now(),
        'Value': value
      }
  )

def run(event, context):
  #TODO: Make http requests async
  url = 'https://www.northwesternenergy.com/get-electricity-generation'
  response = requests.get(url)
  data = response.json().get('Data')
  parsed_data = {}

  min_datapoints = len(data.get(fields[0]).split(','))-1
  for field in fields:
    parsed_data[field] = list(filter(None, data.get(field).split(',')))
    if len(parsed_data[field]) < min_datapoints:
      min_datapoints = len(parsed_data[field])-1

  green_energy = int(parsed_data['LblWindData'][min_datapoints]) + \
                int(parsed_data['LblHydroData'][min_datapoints]) + \
                int(parsed_data['LblSolarData'][min_datapoints])
  dirty_energy = int(parsed_data['LblThermData'][min_datapoints])
  generation = green_energy + dirty_energy
  consumption = int(parsed_data['LblForecastData'][min_datapoints])

  print(f"Date: {parsed_data['LblReadDate'][min_datapoints]}")
  print(f"Green: {green_energy}")
  add_metric('CleanEnergyGeneration', green_energy)
  print(f"Dirty: {dirty_energy}")
  add_metric('FuelEnergyGeneration', dirty_energy)
  print(f"Consumption: {consumption}")
  add_metric('Load', consumption)
  print(f"Green Pct Generation: {(green_energy/generation):.0%}")
  print(f"Green Pct Consumption: {(green_energy/consumption):.0%}")
  print(f"Green Energy Threshold: {green_energy_threshold}%")

  # Record CloudWatch Metrics
  cloudwatch.put_metric_data(
    Namespace='greenplug',
    MetricData=metrics
  )

  # Our rule is to turn on switch when green energy exceeds the threshold
  # and generation exceeds consumption

  switch_desired_on = False
  green_energy_pct = int(round((green_energy/consumption)*100,0))
  if generation > consumption and green_energy_pct >= green_energy_threshold:
    print("Recommend Switch ON")
    switch_desired_on = True
  else:
    print("Recommend switch OFF")

  switch_is_on = False
  try:
    current_status_req = requests.get(f"https://sequematic.com/variable-get/{sequematic_url_suffix}")
    switch_is_on = bool(int(current_status_req.text))
    if switch_is_on:
      print("Switch is currently ON")
    else:
      print("Switch is currently OFF")
  except:
    print("Unable to get switch status")
    return {"statusCode": 500}

  if switch_is_on is not switch_desired_on:
    if switch_desired_on:
      print("Turning switch ON")
      webhook_req = requests.get(f"https://sequematic.com/variable-change/{sequematic_url_suffix}/=1")
    else:
      print("Turning switch OFF")
      webhook_req = requests.get(f"https://sequematic.com/variable-change/{sequematic_url_suffix}/=0")
    if webhook_req.status_code == 200:
      print("Successfully notified sequematic webhook")
      return {"statusCode": 200}

#run({},{})