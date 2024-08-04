from urllib3 import PoolManager
from os import getenv
from boto3 import client
from json import loads
from datetime import datetime as dt
from dateutil import tz
import gzip
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_xray_sdk.core import patch_all

tracer = Tracer()
patch_all(double_patch=True)

if not getenv("AWS_EXECUTION_ENV"):
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

http = PoolManager()
cloudwatch = client("cloudwatch")

metrics = []

default_green_energy_threshold = 80
if getenv("GREEN_ENERGY_THRESHOLD"):
    try:
        green_energy_threshold = int(getenv("GREEN_ENERGY_THRESHOLD"))
        if green_energy_threshold < 0 or green_energy_threshold > 100:
            raise
    except:
        print(
            "GREEN_ENERGY_THRESHOLD must be an integer between 0 and 100.  Default: 80"
        )
        exit(1)
else:
    green_energy_threshold = default_green_energy_threshold

if getenv("SEQUEMATIC_SWITCH_URL_SUFFIX"):
    SEQUEMATIC_SWITCH_URL_SUFFIX = getenv("SEQUEMATIC_SWITCH_URL_SUFFIX")
else:
    print(
        "The environment variable SEQUEMATIC_SWITCH_URL_SUFFIX must be set.  Example: 9999/ABCDF0123/variable_name"
    )
    exit(1)

fields = [
    "LblReadDate",
    "LblWindData",
    "LblHydroData",
    "LblThermData",
    "LblSolarData",
    "LblForecastData",
    "LblTotalData",
]


def add_metric(name, value, timestamp):
    metrics.append(
        {
            "MetricName": name,
            "Dimensions": [{"Name": "zone", "Value": "US-MT-NWE"}],
            "Timestamp": timestamp,
            "Value": value,
        }
    )


def run():
    # TODO: Make http requests async
    url = "https://www.northwesternenergy.com/get-electricity-generation"
    headers = {"Accept-Encoding": "gzip"}
    response = http.request("GET", url, headers=headers)
    data = loads(response.data.decode()).get("Data")
    ts_data = {}
    last_reading = {}
    index = 0

    for field in fields:
        ts_data[field] = data[field].split(",")
        if not ts_data[field][-1]:
            ts_data[field].pop()
        if field == "LblReadDate":
            index = len(ts_data["LblReadDate"]) - 1
        last_reading[field] = ts_data[field][index]

    green_energy = (
        int(last_reading["LblWindData"])
        + int(last_reading["LblHydroData"])
        + int(last_reading["LblSolarData"])
    )
    dirty_energy = int(last_reading["LblThermData"])
    generation = int(last_reading["LblTotalData"])
    consumption = int(last_reading["LblForecastData"])
    timestamp = dt.strptime(last_reading["LblReadDate"], "%m/%d/%y %H:%M").replace(
        tzinfo=tz.gettz("America/Denver")
    )

    print(f"Date: {timestamp.strftime('%m/%d/%y %H:%M %Z')}")
    print(f"Green: {green_energy}")
    add_metric("CleanEnergyGeneration", green_energy, timestamp)
    print(f"Dirty: {dirty_energy}")
    add_metric("FuelEnergyGeneration", dirty_energy, timestamp)
    print(f"Consumption: {consumption}")
    add_metric("Load", consumption, timestamp)
    print(f"Green Pct Generation: {(green_energy/generation):.0%}")
    print(f"Green Pct Consumption: {(green_energy/consumption):.0%}")
    print(f"Green Energy Threshold: {green_energy_threshold}%")

    # Record CloudWatch Metrics
    cloudwatch.put_metric_data(Namespace="greenplug", MetricData=metrics)

    # Our rule is to turn on switch when green energy exceeds the threshold
    # and generation exceeds consumption

    switch_desired_on = False
    green_energy_pct = int(round((green_energy / consumption) * 100, 0))

    if getenv("SEQUEMATIC_VALUE_URL_SUFFIX"):
        SEQUEMATIC_VALUE_URL_SUFFIX = getenv("SEQUEMATIC_VALUE_URL_SUFFIX")
        value = str(green_energy_pct)
        update_var_request = http.request(
            "GET",
            f"https://sequematic.com/variable-change/{SEQUEMATIC_VALUE_URL_SUFFIX}/={value}"
        )
        if update_var_request.status == 200:
            print("Successfully updated green energy value variable")

    if green_energy_pct >= green_energy_threshold:
        print("Recommend Switch ON")
        switch_desired_on = True
    else:
        print("Recommend switch OFF")

    switch_is_on = False
    try:
        current_status_req = http.request(
            "GET", f"https://sequematic.com/variable-get/{SEQUEMATIC_SWITCH_URL_SUFFIX}"
        )
        switch_is_on = bool(int(current_status_req.data.decode()))
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
            webhook_req = http.request(
                "GET",
                f"https://sequematic.com/variable-change/{SEQUEMATIC_SWITCH_URL_SUFFIX}/=1",
            )
        else:
            print("Turning switch OFF")
            webhook_req = http.request(
                "GET",
                f"https://sequematic.com/variable-change/{SEQUEMATIC_SWITCH_URL_SUFFIX}/=0",
            )
        if webhook_req.status == 200:
            print("Successfully notified sequematic webhook")
            return {"statusCode": 200}
    else:
        print("Nothing to do")
        return {"statusCode": 200}


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    return run()


if __name__ == "__main__":
    run()
