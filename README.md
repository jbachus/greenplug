# Greenplug AWS Lambda Function
This function monitors the [Northwestern Energy Montana generation stats](https://www.northwesternenergy.com/clean-energy/where-does-your-energy-come-from/electric-generation) to determine whether there is excess green energy being generated from wind and solar.  It updates a variable on [SEQUEmatic](https://www.sequematic.com) that allows users to subscribe to the sequences and link their smart plugs from Tuya, Sonoff, or Philips hue.

## Use Case
Many of us have electrical appliances that don't require power all the time.  Many electric utilities also have a high volume of intermittent generating sources like wind or solar that are weather dependent.  Shifting this electrical load to times when green energy is abundant reduces the carbon footprint of these appliances and has the added benfits of reducing downstream electrical generation costs by utilizing power that is essentially free.

Some examples of good appliances to put behind a green plug are chargers (sporadically used laptops, tablets, e-readers, headphones, battery-powered lawn equipment, tools).  You could also use it to signal when to run the dishwasher or laundry washer/dryer (at least when you can't line dry).

## Usage
To use these sequences, sign up for an account at [SEQUEmatic](https://www.sequematic.com).  Once you have [linked services](https://sequematic.com/services) with your smart plugs, you can import the following sequences and update the triggers for your own smart plugs:
- [Turn on switch when there is excess green energy in Montana](https://sequematic.com/import-sequence/21377)
- [Turn off switch when there is not excess green energy in Montana](https://sequematic.com/import-sequence/21378)
