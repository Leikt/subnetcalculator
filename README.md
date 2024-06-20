# Subnetcalculator

## Installation

CLone this repository in local.

Create a virtual environment and install the packages:
```shell
python -m venv .env.windows
.env.windows/Scripts/activate
pip install pyyaml pydantic
```


Run `python subnetcalculator/subnetcalculator.py --help`

This should display:

```
usage: subnetcalculator [-h] [--generate-json-schema] [--generate-example {simple,advanced,company}] [--out-stdin] [--out-txt FILE] [--out-json FILE] [--out-yaml FILE] target

positional arguments:
  target                Configuration file to use for the subnet structure generation. Or destination file if --generate-json-schema or --generate-example is set.

options:
  -h, --help            show this help message and exit
  --generate-json-schema
                        Generate the json schema to the given file.
  --generate-example {simple,advanced,company}
                        Generate an example configuration file.
  --out-stdout           Render the computation to the STDIN using print.
  --out-txt FILE        Store the output the given txt file.
  --out-json FILE       Store the output the given json file.
  --out-yaml FILE       Store the output the given yaml file.
```

## Generate a configuration example

> Always activate the environment first: `.env.windows/Scripts/activate`

`python subnetcalculator/subnetcalculator.py --generate-example simple yourfile.yaml`

That will create a sample configuration file `yourfile.yaml`.

## Compute subnets

> Always activate the environment first: `.env.windows/Scripts/activate`

`python subnetcalculator/subnetcalculator.py --out-stdout yourfile.yaml`

That will compute the subnets and display them in the standard output.

```
NAME                CIDR                     ADDRCOUNT      FIRSTADDR           LASTADDR            DESCRIPTION                                       
PUBLIC              10.1.0.0/18              16384          10.1.0.0            10.1.63.255         Hosts internet facing resources.
PRIVATE             10.1.64.0/18             16384          10.1.64.0           10.1.127.255        Hosts compute resources.
DATA                10.1.128.0/18            16384          10.1.128.0          10.1.191.255        Hosts databases.
```

> You can add `--out-yaml youroutput.yaml` to put the result in a yaml file that can used by other scripts.