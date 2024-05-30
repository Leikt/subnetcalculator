import argparse
import json
import math
from ipaddress import IPv4Network
from pathlib import Path
from typing import Literal

try:
    import yaml
    from pydantic import BaseModel, Field
except ImportError:
    print('Install the following packages')
    print('pydantic>=2.7.2,<3')
    print('PyYaml>=6.0.0,<7.0.0')
    exit(1)


class SubnetCountError(Exception):
    pass


class SubnetMetadata(BaseModel, extra='forbid'):
    name: str = Field(description='Subnet name', default=None)
    description: str = Field(description='Subnet description', default=None)
    tier: str = Field(description='Subnet tier', default=None, examples=['public', 'private', 'data'])


StructureType = list[list | str | dict[Literal["__placeholder__"], int]]


class NetworkStructureConfiguration(BaseModel, extra='forbid'):
    network_cidr: IPv4Network = Field(
        examples=['10.12.0.0/16', '10.0.0.0/8'],
        description='Top-level subnet CIDR.'
    )
    metadata: dict[str, SubnetMetadata] = Field(
        description='Metadata describing the subnets by ids.',
        default_factory=dict
    )
    structure: StructureType = Field(
        description='Subnet structure'
    )


class Calculator:
    def __init__(
            self,
            configuration: NetworkStructureConfiguration,
            default_metadata: SubnetMetadata = None
    ) -> None:
        self.config = configuration
        self.result: dict[str, IPv4Network] = {}
        if default_metadata is None:
            self.default_metadata = SubnetMetadata(name='---', description='---', tier='')
        else:
            self.default_metadata = default_metadata

    def compute(self) -> dict[str, IPv4Network]:
        self._compute(self.config.network_cidr, self.config.structure)
        return self.result

    def _compute(self, parent_subnet: IPv4Network, structure: StructureType) -> None:
        structure_len = self.find_structure_len(structure)
        prefix = self.find_prefix(structure_len)
        if prefix + parent_subnet.prefixlen > 32:
            raise ValueError(f'Too many subnets! (Prefix is {prefix + parent_subnet.prefixlen})')

        child_subnets = list(parent_subnet.subnets(prefix))
        for i, structure_item in enumerate(structure):
            child_subnet = child_subnets[i]
            if structure_item in [None, '__placeholder__']:
                continue
            elif isinstance(structure_item, list):
                self._compute(child_subnet, structure_item)
            elif isinstance(structure_item, dict):
                continue
            else:
                self.result[structure_item] = child_subnet

    @classmethod
    def find_structure_len(cls, structure: StructureType):
        count = 0
        for item in structure:
            if isinstance(item, dict):
                count += item['__placeholder__']
            else:
                count += 1
        return count

    @staticmethod
    def find_prefix(value: int) -> int:
        for i in range(0, 32):
            if value <= math.pow(2, i):
                return i
        raise ValueError(f'Cannot find prefix for {value}.')


class SubnetInfo(BaseModel, extra='forbid'):
    id: str
    name: str
    description: str
    cidr: IPv4Network
    first_address: str
    last_address: str


class Exporter:
    def __init__(
            self,
            config: NetworkStructureConfiguration,
            structure: dict[str, IPv4Network],
            default_metadata: SubnetMetadata = None
    ) -> None:
        self.config = config
        self.structure = structure
        self.default_metadata = default_metadata if default_metadata else SubnetMetadata(name='', description='---',
                                                                                         tier='---')
        self.data: list[SubnetInfo] = []
        self.build_data()

    def build_data(self):
        if len(self.data) > 0:
            return

        for subnet_id, subnet_cidr in self.structure.items():
            subnet_metadata = self.config.metadata.get(subnet_id, self.default_metadata)
            subnet_result = SubnetInfo(
                id=subnet_id,
                name=subnet_metadata.name if len(subnet_metadata.name) > 0 else subnet_id,
                cidr=subnet_cidr,
                description=subnet_metadata.description,
                first_address=subnet_cidr[0].compressed,
                last_address=subnet_cidr[-1].compressed
            )
            self.data.append(subnet_result)

    def export_txt(self) -> str:
        result = [
            f'{"NAME":<20}{"CIDR":<25}{"ADDRCOUNT":<15}{"FIRSTADDR":<20}'
            f'{"LASTADDR":<20}{"DESCRIPTION":<50}'
        ]
        for info in self.data:
            result.append(
                f'{info.name:<20}'
                f'{info.cidr.compressed:<25}'
                f'{info.cidr.num_addresses:<15}'
                f'{info.first_address:<20}'
                f'{info.last_address:<20}'
                f'{info.description:<50}'
            )
        return '\n'.join(result)

    def to_dict(self) -> dict:
        return {
            'network_cidr': self.config.network_cidr.compressed,
            'subnets': [dict(
                id=info.id,
                name=info.name,
                cidr=info.cidr.compressed,
                description=info.description,
                first_address=info.first_address,
                last_address=info.last_address
            ) for info in self.data]
        }


def parse_cli_arguments():
    parser = argparse.ArgumentParser(prog='subnetcalculator')
    parser.add_argument(
        'target',
        help='Configuration file to use for the subnet structure generation. '
             'Or destination file if --generate-json-schema or --generate-example is set.',
    )
    parser.add_argument(
        '--generate-json-schema', default=False, action='store_true',
        help='Generate the json schema to the given file.'
    )
    parser.add_argument(
        '--generate-example', default=None, choices=['simple', 'advanced', 'company'],
        help='Generate an example configuration file.'
    )
    parser.add_argument(
        '--out-stdin', default=False, action='store_true',
        help='Render the computation to the STDIN using print.'
    )
    parser.add_argument(
        '--out-txt', default=None, type=Path, metavar='FILE',
        help='Store the output the given txt file.'
    )
    parser.add_argument(
        '--out-json', default=None, type=Path, metavar='FILE',
        help='Store the output the given json file.'
    )
    parser.add_argument(
        '--out-yaml', default=None, type=Path, metavar='FILE',
        help='Store the output the given yaml file.'
    )
    args = parser.parse_args()
    return args


def cli():
    args = parse_cli_arguments()

    if args.generate_json_schema:
        schema = NetworkStructureConfiguration.schema_json(indent=4)
        Path(args.target).write_text(schema, encoding='utf-8')
        return

    if args.generate_example is not None:
        example = EXAMPLES.get(args.generate_example)
        Path(args.target).write_text(example, encoding='utf-8')
        return

    configuration_raw = yaml.safe_load(Path(args.target).read_text(encoding='utf-8'))
    configuration = NetworkStructureConfiguration(**configuration_raw)

    calculator = Calculator(configuration)
    network_structure = calculator.compute()

    exporter = Exporter(configuration, network_structure)
    if args.out_stdin:
        txt = exporter.export_txt()
        print(txt)

    if args.out_txt:
        txt = exporter.export_txt()
        args.out_txt.write_text(txt, encoding='utf-8')

    if args.out_json:
        data = exporter.to_dict()
        args.out_json.write_text(json.dumps(data, indent=4), encoding='utf-8')

    if args.out_yaml:
        data = exporter.to_dict()
        args.out_yaml.write_text(yaml.safe_dump(data), encoding='utf-8')


EXAMPLE_SIMPLE = """network_cidr: 10.1.0.0/16
structure:
    - public
    - private
    - data
metadata:
    public:
        name: PUBLIC
        description: Hosts internet facing resources.
    private:
        name: PRIVATE
        description: Hosts compute resources.
    data:
        name: DATA
        description: Hosts databases.
"""

EXAMPLE_ADVANCED = """network_cidr: 10.1.0.0/16
structure:
    - - - data-1
        - data-2
        - __placeholder__
      - - public-1
        - public-2
        - __placeholder__
      - - internal-1
        - internal-2
        - __placeholder__
    - compute-1
    - compute-2
    - __placeholder__
metadata:
    data-1:
        name: DATA-1
        description: Hosts databases and critical assets that are hosting data in AZ1
        tier: data
    data-2:
        name: DATA-2
        description: Hosts databases and critical assets that are hosting data in AZ2
        tier: data
    public-1:
        name: PUBLIC-1
        description: Hosts internet facing assets in AZ1
        tier: public
    public-2:
        name: PUBLIC-2
        description: Hosts internet facing assets in AZ2
        tier: public
    internal-1:
        name: INTERNAL-1
        description: Hosts company VPN facing assets in AZ1
        tier: private
    internal-2:
        name: INTERNAL-2
        description: Hosts company VPN facing assets in AZ2
        tier: private
    compute-1:
        name: COMPUTE-1
        description: Hosts computing assets in AZ1
        tier: private
    compute-2:
        name: COMPUTE-2
        description: Hosts computing assets in AZ2
        tier: private
"""

EXAMPLE_COMPANY_NETWORK = """network_cidr: 10.0.0.0/8
structure:
  - vpc-1
  - vpc-2
  - - - - vpc-3-data-1
        - vpc-3-data-2
        - __placeholder__
      - - vpc-3-public-1
        - vpc-3-public-2
        - __placeholder__
    - vpc-3-compute-1
    - __placeholder__: 2
  - __placeholder__: 253
metadata:
  vpc-1:
    name: VPC-1
    description: The whole VPC-1 network
  vpc-2:
    name: VPC-2
    description: The whole VPC-2 network
  vpc-3-data-1:
    name: VPC-3-DATA-1
    description: Host VPC-3 databases in AZ1
  vpc-3-data-2:
    name: VPC-3-DATA-2
    description: Host VPC-3 databases in AZ2
  vpc-3-public-1:
    name: VPC-3-PUBLIC-1
    description: Host VPC-3 internet facing assets in AZ1
  vpc-3-public-2:
    name: VPC-3-PUBLIC-2
    description: Host VPC-3 internet facing assets in AZ2
  vpc-3-compute-1:
    name: VPC-3-COMPUTE-2
    description: Host VPC-3 computing assets in AZ1
"""

EXAMPLES = {
    'simple': EXAMPLE_SIMPLE,
    'advanced': EXAMPLE_ADVANCED,
    'company': EXAMPLE_COMPANY_NETWORK,
}

if __name__ == '__main__':
    cli()
