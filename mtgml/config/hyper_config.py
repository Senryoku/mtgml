from dataclasses import dataclass
from typing import Generic, TypeVar, Union

import yaml
from tensorflow.keras.utils import register_keras_serializable

from mtgml.layers.configurable_layer import ConfigurableLayer

ValueType = TypeVar('ValueType', float, int, str, bool, list, 'HyperConfig')
LayerType = TypeVar('LayerType', bound=ConfigurableLayer)
LayerType2 = TypeVar('LayerType2', bound=ConfigurableLayer)


@register_keras_serializable(package='mtgml.config', name='HyperConfigValue')
@dataclass
class HyperConfigValue(Generic[ValueType]):
    help: str
    min: Union[ValueType, None] = None
    max: Union[ValueType, None] = None
    step: Union[ValueType, None] = None
    logdist: Union[bool, None] = None
    choices: Union[tuple[ValueType], None] = None
    value: Union[ValueType, None] = None

    @classmethod
    def from_config(cls, config):
        return cls(help=config.get('help'), min=config.get('min'), max=config.get('max'),
                   step=config.get('step'), logdist=config.get('logdist'),
                   choices=config.get('choices'), value=config.get('value'))

    def get_config(self):
        config = {'help': self.help, 'value': self.value}
        # if self.min is not None:
        #     config['min'] = self.min
        # if self.max is not None:
        #     config['max'] = self.max
        # if self.step is not None:
        #     config['step'] = self.step
        # if self.logdist is not None:
        #     config['logdist'] = self.logdist
        if self.choices is not None:
            config['choices'] = self.choices
        return config


@register_keras_serializable(package='mtgml.config', name='HyperConfig')
class HyperConfig(Generic[LayerType]):
    def __init__(self, data: dict[str, HyperConfigValue] = {}, layer_type: Union[type[LayerType], None] = None,
                 fixed: dict = {}, seed: int = 5723):
        self.data = dict(data)
        self.layer_type = layer_type
        self.fixed = fixed
        self.seed = seed

    def get_int(self, name: str, *, default: Union[int, None], help: str,
                min: Union[int, None] = None, max: Union[int, None] = None,
                step: Union[int, None] = None, logdist: Union[bool, None] = None) -> int:
        if name in self.fixed:
            return self.fixed[name]
        if name in self.data:
            if self.data[name].value is not None:
                return self.data[name].value
        else:
            self.data[name] = HyperConfigValue(help=help, min=min, max=max, step=step,
                                               logdist=logdist, value=default)
        return default

    def get_float(self, name: str, *, default: Union[float, None], help: str,
                  min: Union[float, None] = None, max: Union[float, None] = None,
                  step: Union[float, None] = None, logdist: Union[bool, None] = None) -> Union[float, None]:
        if name in self.fixed:
            return self.fixed[name]
        if name in self.data:
            if self.data[name].value is not None:
                return self.data[name].value
        else:
            self.data[name] = HyperConfigValue(help=help, min=min, max=max, step=step,
                                               logdist=logdist, value=default)
        return default

    def get_bool(self, name: str, *, default: bool, help: str) -> bool:
        if name in self.fixed:
            return self.fixed[name]
        if name in self.data:
            if self.data[name].value is not None:
                return self.data[name].value
        else:
            self.data[name] = HyperConfigValue(help=help, value=default)
        return default

    def get_list(self, name: str, *, default: Union[list, None], help: str) -> Union[list, None]:
        if name in self.fixed:
            return self.fixed[name]
        if name in self.data:
            if self.data[name].value is not None:
                return self.data[name].value
        else:
            self.data[name] = HyperConfigValue(help=help, value=default)
        return default

    def get_choice(self, name: str, *, default: Union[ValueType, None], choices=list[ValueType],
                   help: str) -> Union[ValueType, None]:
        if name in self.fixed:
            return self.fixed[name]
        if name in self.data:
            if self.data[name].value is not None:
                return self.data[name].value
        else:
            self.data[name] = HyperConfigValue(help=help, choices=choices, value=default)
        return default

    def get_sublayer_config(self, name: str, *, sub_layer_type: type[LayerType2], help: str,
                            seed_mod: int = 7, fixed: dict = {}) -> 'HyperConfig':
        if name in self.fixed:
            value = self.fixed[name]
            if isinstance(value, HyperConfig):
                return value
            value = dict(value)
            value.update(fixed)
            fixed = value
        if name in self.data:
            if self.data[name].value is not None:
                self.data[name].value.fixed = fixed
                return self.data[name].value
        config = HyperConfig(layer_type=sub_layer_type, data={}, fixed=fixed, seed=self.seed * seed_mod)
        self.data[name] = HyperConfigValue(help=help, value=config)
        return config

    def get_sublayer(self, name: str, *, sub_layer_type: type[LayerType2], help: str, seed_mod=7,
                            fixed: dict = {}) -> LayerType2:
        config = self.get_sublayer_config(name, sub_layer_type=sub_layer_type, help=help,
                                          seed_mod=seed_mod, fixed=fixed)
        return sub_layer_type(config, name=name)

    def build(self, *args, **kwargs) -> LayerType:
        if self.layer_type is not None:
            self.layer_type.get_properties(self, input_shapes=None)
            for value in self.data.values():
                if value is not None and isinstance(value.value, HyperConfig):
                    value.value.build()
            return self.layer_type(self, *args, **kwargs)

    def get_config(self) -> dict:
        return self.data

    @property
    def seed(self):
        return self.data['seed'].value

    @seed.setter
    def seed(self, value):
        self.data['seed'] = HyperConfigValue(value=value, help='The seed for the rng')

    @classmethod
    def from_config(cls, config) -> 'HyperConfig':
        return cls(data=config['data'], layer_type=None, fixed=config['fixed'], seed=config['seed'])


def value_representer(dumper, data):
    return dumper.represent_mapping(u'!hcv', data.get_config())


def value_constructor(loader, node):
    kwargs = loader.construct_mapping(node)
    return HyperConfigValue(**kwargs)


def config_representer(dumper, data):
    return dumper.represent_mapping(u'!hc', data.get_config())


def config_constructor(loader, node):
    kwargs = loader.construct_mapping(node)
    return HyperConfig(data=kwargs)


yaml.add_representer(HyperConfigValue, value_representer)
yaml.add_constructor(u'!hcv', value_constructor)
yaml.add_representer(HyperConfig, config_representer)
yaml.add_constructor(u'!hc', config_constructor)
