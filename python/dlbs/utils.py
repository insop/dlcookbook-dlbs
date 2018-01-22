# (c) Copyright [2017] Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Two classes are define here :py:class:`dlbs.IOUtils` and :py:class:`dlbs.DictUtils`.
"""

import os
import copy
import json
import re
import logging
import subprocess
import importlib
from multiprocessing import Process
from multiprocessing import Queue
from glob import glob
from dlbs.exceptions import ConfigurationError


class IOUtils(object):
    """Container for input/output helpers"""

    @staticmethod
    def mkdirf(file_name):
        """Makes sure that parent folder of this file exists.

        The file itself may not exist. A typical usage is to ensure that we can
        write to this file. If path to parent folder does not exist, it will be
        created.
        See documentation for :py:func:`os.makedirs` for more details.

        :param str file_name: A name of the file for which we want to make sure\
                              its parent directory exists.
        """
        dir_name = os.path.dirname(file_name)
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)

    @staticmethod
    def find_files(directory, file_name_pattern, recursively=False):
        """Find files in a directory, possibly, recursively.

        Find files which names satisfy *file_name_pattern* pattern in folder
        *directory*. If *recursively* is True, scans subfolders as well.

        :param str directory: A directory to search files in.
        :param str file_name_pattern: A file name pattern to search.
        :param bool recursively: If True, search in subdirectories.
        :return: List of file names satisfying *file_name_pattern* pattern.
        """
        if not recursively:
            files = [f for f in glob(os.path.join(directory, file_name_pattern))]
        else:
            files = [f for p in os.walk(directory) for f in glob(os.path.join(p[0], file_name_pattern))]
        return files


class DictUtils(object):
    """Container for dictionary helpers."""

    @staticmethod
    def ensure_exists(dictionary, key, default_value=None):
        """ Ensures that the dictionary *dictionary* contains key *key*

        If key does not exist, it adds a new item with value *default_value*.
        The dictionary is modified in-place.

        :param dict dictionary: Dictionary to check.
        :param str key: A key that must exist.
        :param obj default_value: Default value for key if it does not exist.
        """
        if key not in dictionary:
            dictionary[key] = copy.deepcopy(default_value)

    @staticmethod
    def lists_to_strings(dictionary, separator=' '):
        """ Converts every value in dictionary that is list to strings.

        For every item in *dictionary*, if type of a value is 'list', converts
        this list into a string using separator *separator*.
        The dictictionary is modified in-place.

        :param dict dictionary: Dictionary to modify.
        :param str separator: An item separator.
        """
        for key in dictionary:
            if isinstance(dictionary[key], list):
                dictionary[key] = separator.join(str(elem) for elem in dictionary[key])

    @staticmethod
    def filter_by_key_prefix(dictionary, prefix, remove_prefix=True):
        """Creates new dictionary with items which keys start with *prefix*.

        Creates new dictionary with items from *dictionary* which keys
        names starts with *prefix*. If *remove_prefix* is True, keys in new
        dictionary will not contain this prefix.
        The dictionary *dictionary* is not modified.

        :param dict dictionary: Dictionary to search keys in.
        :param str prefix: Prefix of keys to be extracted.
        :param bool remove_prefix: If True, remove prefix in returned dictionary.
        :return: New dictionary with items which keys names start with *prefix*.
        """
        return_dictionary = {}
        for key in dictionary:
            if key.startswith(prefix):
                return_key = key[len(prefix):] if remove_prefix else key
                return_dictionary[return_key] = copy.deepcopy(dictionary[key])
        return return_dictionary

    @staticmethod
    def dump_json_to_file(dictionary, file_name):
        """ Dumps *dictionary* as a json object to a file with *file_name* name.

        :param dict dictionary: Dictionary to serialize.
        :param str file_name: Name of a file to serialie dictionary in.
        """
        if file_name is not None:
            IOUtils.mkdirf(file_name)
            with open(file_name, 'w') as file_obj:
                json.dump(dictionary, file_obj, indent=4)

    @staticmethod
    def add(dictionary, iterable, pattern, must_match=True, add_only_keys=None):
        """ Updates *dictionary* with items from *iterable* object.

        This method modifies/updates *dictionary* with items from *iterable*
        object. This object must support ``for something in iterable`` (list,
        opened file etc). Only those items in *iterable* are considered, that match
        *pattern* (it's a regexp epression). If a particular item does not match,
        and *must_match* is True, *ConfigurationError* exception is thrown.

        Regexp pattern must return two groups (1 and 2). First group is considered
        as a key, and second group is considered to be value. Values must be a
        json-parseable strings.

        If *add_only_keys* is not None, only those items are added to *dictionary*,
        that are in this list.

        Existing items in *dictionary* are overwritten with new ones if key already
        exists.

        One use case to use this method is to populate a dictionary with key-values
        from log files.

        :param dict dictionary: Dictionary to update in-place.
        :param obj iterable: Iterable object (list, opened file name etc).
        :param str patter: A regexp pattern for matching items in ``iterable``.
        :param bool must_match: Specifies if every element in *iterable* must match\
                                *pattern*. If True and not match, raises exception.
        :param list add_only_keys: If not None, specifies keys that are added into\
                                   *dictionary*. Others are ignored.

        :raises ConfigurationError: If *must_match* is True and not match or if value\
                                    is not a json-parseable string.
        """
        matcher = re.compile(pattern)
        for line in iterable:
            match = matcher.match(line)
            if not match:
                if must_match:
                    raise ConfigurationError("Cannot match key-value from '%s' with pattern '%s'. Must match is set to true" % (line, pattern))
                else:
                    continue
            key = match.group(1).strip()
            try:
                value = match.group(2).strip()
                value = json.loads(value) if len(value) > 0 else None
            except ValueError as e:
                raise ConfigurationError("Cannot parse JSON string '%s' with key '%s' (key-value definition: '%s'). Error is %s" % (value, key, line, str(e)))
            if add_only_keys is None or key in add_only_keys:
                dictionary[key] = value
                logging.debug("Key-value item (%s=%s) has been parsed and added to dictionary", key, str(value))

    @staticmethod
    def match(dictionary, query, policy='relaxed', matches=None):
        """ Match *query* against *dictionary*.

        The *query* and *dictionary* are actually dictionaries. If policy is 'strict',
        every key in query must exist in dictionary with the same value to match.
        If policy is 'relaxed', dictionary may not contain all keys from query
        to be matched. In this case, the intersection of keys in dictionary and query
        is used for matching.

        It's assuemd we match primitive types such as numbers and strings not
        lists or dictionaries. If values in query are lists, then condition OR applies.
        For instance:

        match(dictionary, query = { "framework": "tensorflow" }, policy='strict')
           Match dictionary only if it contains key 'framework' with value "tensorflow".
        match(dictionary, query = { "framework": "tensorflow" }, policy='relaxed')
           Match dictionary if it does not contain key 'framework' OR contains\
           key 'framework' with value "tensorflow".
        match(dictionary, query = { "framework": ["tensorflow", "caffe2"] }, policy='strict')
           Match dictionary only if it contains key 'framework' with value "tensorflow" OR\
           "caffe2".
        match(dictionary, query = { "framework": ["tensorflow", "caffe2"], "batch": [16, 32] }, policy='strict')
           Match dictionary only if it (a) contains key 'framework' with value "tensorflow" OR "caffe2"\
           and (b) it contains key 'batch' with value 16 OR 32.

        :param dict dictionary: Dictionary to match.
        :param dict query: Query to use.
        :param ['relaxed', 'strict'] policy: Policy to match.
        :param dict matches: Dictionary where matches will be stored if match has been identified.
        :return: True if match
        :rtype: bool
        """
        assert policy in ['relaxed', 'strict'], ""

        for field, value in query.iteritems():
            if field not in dictionary:
                if policy == 'relaxed':
                    continue
                else:
                    return False
            if isinstance(value, list) or not isinstance(value, basestring):
                values = value if isinstance(value, list) else [value]
                if dictionary[field] not in values:
                    return False
                if matches is not None:
                    matches['%s_0' % (field)] = dictionary[field]
            else:
                match = re.compile(value).match(dictionary[field])
                if not match:
                    return False
                else:
                    if matches is not None:
                        matches['%s_0' % (field)] = dictionary[field]
                        for index, group in enumerate(match.groups()):
                            matches['%s_%d' % (field, index+1)] = group
                    continue
        return True

class ConfigurationLoader(object):
    """Loads experimenter configuration from multiple files."""

    @staticmethod
    def load(path, files=None):
        """Loads configurations (normally in `conigs`) folder.

        :param str path: Path to load configurations from
        :param list files: List of file names to load. If None, all files with
                           JSON extension in **path** are loaded.
        :return: A tuple consisting of a list of config files, configuration
                 object (dictionary) and dictionary of parameters info

        This method loads configuration files located in 'path'. If `files` is
        empty, all json files are loaded from that folder.
        This method fails if one parameter is defined in multiple files. This
        is intended behaviour for now (this also applies for update_param_info method).
        """
        assert path is not None, "The 'path' parameter in ConfigurationLoader::load cannot be null."
        assert os.path.isdir(path), "The 'path' parameter (%s) in ConfigurationLoader::load must point to existing directory" % path
        if files is not None:
            config_files = [os.path.join(path, f) for f in files]
        else:
            config_files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.json')]
        config = {}         # Configuration with params/vars/extensions
        param_info = {}     # Information on params such as type and help messages
        for config_file in config_files:
            logging.debug('Loading configuration from: %s', config_file)
            with open(config_file) as file_obj:
                try:
                    # A part of global configuration from this particular file
                    config_section = json.load(file_obj)
                    # Update parameters info.
                    ConfigurationLoader.update_param_info(param_info, config_section, is_user_config=False)
                    # Joing configuration from this single file.
                    ConfigurationLoader.update(config, ConfigurationLoader.remove_info(config_section))
                except ValueError as error:
                    logging.error("Invalid JSON configuration in file %s", config_file)
                    raise error
        return (config_files, config, param_info)


    @staticmethod
    def update_param_info(param_info, config, is_user_config=False):
        """Update parameter info dictionary based on configurationi in **config**

        :param dict param_info: A parameter info dictionary that maps parameter
                                name to its description dictionary that contains
                                such fileds as value, help message, type, constraints
                                etc.
        :param dict config: A dictionary with configuration section that may contain
                            parameters, variables and extensions. The **config** is
                            a result of parsing a JSON configuration file.
        :param bool is_user_config: If True, the config object represents user-provided
                                    configuration. If False, this is a system configuration.
                                    Based on this flag, we deal with parameters in config
                                    that redefine parameters in existing param_info
                                    differently. See comments below.

        We are interested here only in parameters section where parameter information
        is defined. There are two scenarios this method is used:
          1. Load standard configuration. In this case, parameter redefinition is
             prohibited. If `parameters` section in `config` redefines existing
             parameters in param_info (already loaded params), program terminates.
          2. Load user-provided configuration. In this case, we still update parameter
             info structure, but deal with it in slightly different way. If parameter in
             `config` exists in param_info, it means user has provided their specific
             value for this parameter.

        Types of user defined parameters are defined either by user in a standard way as
        we define types for standard parameters or induced automatically based on JSON
        parse result.
        """
        if 'parameters' not in config:
            return
        params = config['parameters']
        for name in params:
            val = params[name]
            if not is_user_config:
                # If this is not a user-provided configuration, we disallow parameter redefinition.
                assert name not in param_info,\
                       "Trying to redefine parameter (%s). Cur val is '%s', new val is '%s'" % (name, str(param_info[name]), val)
            if isinstance(val, dict):
                # This is a complete parameter definition with name, value and description.
                assert 'val' in val, "Invalid parameter (%s) definition. In case of dictionary, it must define a 'val' field." % name
                if name not in param_info:
                    param_info[name] = copy.deepcopy(val)  # New parameter, set it info object.
                else:
                    logging.warn(
                        "User provided parameter (%s) entirely redefines existing parameter (%s). Normally, only value needs to be provided.",
                        json.dumps(val),
                        json.dumps(param_info[name])
                    )
                    param_info[name]['val'] = val['val']   # Existing parameter from user configuration, update its value
            else:
                # Just parameter value
                val_type = 'str' if isinstance(val, basestring) or isinstance(val, list) else type(val).__name__
                assert val_type in ('int', 'str', 'float', 'bool'),\
                       "Unsupported type of a parameter %s" % val_type
                if name not in param_info:
                    param_info[name] = {
                        'val': val,
                        'type': val_type,
                        'desc': "No description for this parameter provided (it was automatically converted from its value)."
                    }
                else:
                    param_info[name]['val'] = val

    @staticmethod
    def remove_info(config):
        """In parameter section of a **config** the function removes parameter info
        leaving only their values

        :param dict config: A dictionary with configuration section that may contain
                            parameters, variables and extensions. The **config** is
                            a result of parsing a JSON configuration file.
        :return: A copy of **config** with info removed
        """
        clean_config = copy.deepcopy(config)

        if 'parameters' in clean_config:
            params = clean_config['parameters']
            for name in params:
                val = params[name]
                if isinstance(val, dict):
                    assert 'val' in val, "Invalid parameter (%s) definition. In case of dictionary, it must define a 'val' field." % name
                    params[name] = val['val']

        return clean_config

    @staticmethod
    def update(dest, source, is_root=True):
        """Merge **source** dictionary into **dest** dictionary assuming source
        and dest are JSON configuration configs or their members.

        :param dict dest: Merge data to this dictionary.
        :param dict source: Merge data from this dictionary.
        :param bool is_root: True if **dest** and *source** are root configuration
                             objects. False if these objects are members.
        """
        for key in source:
            if key not in dest:
                dest[key] = copy.deepcopy(source[key])
            else:
                both_dicts = isinstance(dest[key], dict) and isinstance(source[key], dict)
                both_lists = isinstance(dest[key], list) and isinstance(source[key], list)
                both_primitive = type(dest[key]) is type(source[key]) and isinstance(dest[key], (basestring, int, float, long))

                if is_root:
                    assert both_dicts or both_lists, "In root configuration objects, only dictionaries and lists are allowed."
                    if both_dicts:
                        # This is for parameters and variables section
                        ConfigurationLoader.update(dest[key], source[key], is_root=False)
                    else:
                        # This works for extensions
                        dest[key].extend(source[key])
                else:
                    assert both_lists or both_primitive, "Members of configuration must be either lists or primitive types"
                    dest[key] = copy.deepcopy(source[key]) if both_lists else source[key]


class ResourceMonitor(object):
    """The class is responsible for launching/shutting down/communicating with
    external resource manager that monitors system resource consumption.

    proc_pid date virt res shrd cpu mem power gpus_power
    """
    def __init__(self, launcher, pid_folder, frequency, fields_specs):
        """Initializes resource monitor but does not create queue and process.

        :param str launcher: A full path to resource monitor script.
        :param str pid_folder: A full path to folder where pid file is created. The
                               file name is fixed and its value is `proc.pid`.
        :param float frequency: A sampling frequency in seconds. Can be something like
                                0.1 seconds
        """
        self.launcher = launcher
        self.pid_file = os.path.join(pid_folder, 'proc.pid')
        self.frequency = frequency
        self.queue = None
        self.monitor_process = None
        # Parse fields specs
        # time:str:1,mem_virt:float:2,mem_res:float:3,mem_shrd:float:4,cpu:float:5,mem:float:6,power:float:7,gpus:float:8:
        self.fields = {}
        raw_fields = fields_specs.split(',')
        for raw_field in raw_fields:
            fields_split = raw_field.split(':')
            assert len(fields_split) in (3, 4),\
                   "Invalid format of field specification (%s). Must be name:type:index, name:type:index: or name:type:index:count" % raw_field
            field_name = fields_split[0]
            assert field_name not in self.fields,\
                   "Found duplicate timeseries field (%s)" % field_name
            field_type = fields_split[1]
            assert field_type in ('str', 'int', 'float', 'bool'),\
                   "Invalid field type (%s). Must be one of ('str', 'int', 'float', 'bool')" % field_type
            index = int(fields_split[2])
            if len(fields_split) == 3:
                count = -1
            elif fields_split[3] == '':
                count = 0
            else:
                count = int(fields_split[3])
            self.fields[field_name] = {
                'type': field_type,
                'index': index,
                'count': count
            }

    @staticmethod
    def monitor_function(launcher, pid_file, frequency, queue):
        """A main monitor worker function.

        :param str launcher: A full path to resource monitor script.
        :param str pid_folder: A full path to folder where pid file is created. The
                               file name is fixed and its value is `proc.pid`.
        :param float frequency: A sampling frequency in seconds. Can be something like
                                0.1 seconds
        :param multiprocessing.Queue queue: A queue to communicate measurements.

        A resource monitor is launched as a subprocess. The thread is reading its
        output and will put the data into a queue. A main thread will then dequeue all
        data at once once experiment is completed.
        """
        cmd = [
            launcher,
            pid_file,
            '',
            str(frequency)
        ]
        process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # The 'output' is a string printed out by a resource monitor
                # script. It's a whitespace separated string of numbers.
                queue.put(output.strip())

    @staticmethod
    def str_to_type(str_val, val_type):
        if val_type == 'str':
            return str_val
        elif val_type == 'int':
            return int(str_val)
        elif val_type == 'float':
            return float(str_val)
        elif val_type == 'bool':
            v = str_val.lower()
            assert v in ('true', 'false', '1', '0', 'on', 'off'),\
                   "Invalid boolean value in string (%s)" % str_val
            return v in ('true', 1, 'on')
        else:
            assert False, "Invalid value type %s" % val_type

    def get_measurements(self):
        """Dequeue all data, put it into lists and return them.
        time:str:1,mem_virt:float:2,mem_res:float:3,mem_shrd:float:4,cpu:float:5,mem:float:6,power:float:7,gpus:float:8-

        :return: Dictionary that maps metric field to a time series of its value.
        """
        metrics = {}
        for key in self.fields.keys():
            metrics[key] = []
        # What's in output:
        #  proc_pid date virt res shrd cpu mem power gpus_power
        while not self.queue.empty():
            data = self.queue.get().strip().split()
            for field in self.fields:
                tp = self.fields[field]['type']
                idx = self.fields[field]['index']
                count = self.fields[field]['count']
                if count == -1:
                    metrics[field].append(ResourceMonitor.str_to_type(data[idx], tp))
                elif count == 0:
                    metrics[field].append([ResourceMonitor.str_to_type(data[idx], tp)])
                else:
                    metrics[field].append([
                        ResourceMonitor.str_to_type(data[index], tp) for index in xrange(idx, idx+count)
                    ])
        return metrics

    def remove_pid_file(self):
        """Deletes pif file from disk."""
        try:
            os.remove(self.pid_file)
        except OSError:
            pass

    def empty_pid_file(self):
        """Empty pid file."""
        try:
            with open(self.pid_file, 'w'):
                pass
        except IOError:
            pass

    def write_pid_file(self, pid):
        """Write the pid into pid file.

        :param int pid: A pid to write.

        This is a debugging function and most likely should not be used.
        """
        with open(self.pid_file, 'w') as fhandle:
            fhandle.write('%d' % pid)

    def run(self):
        """Create queue and start resource monitor in background thread.

        Due to possible execution of benchmarks in containers, we must not delete
        file here, but create or empty it in host OS.
        """
        self.empty_pid_file()
        self.queue = Queue()
        self.monitor_process = Process(
            target=ResourceMonitor.monitor_function,
            args=(self.launcher, self.pid_file, self.frequency, self.queue)
        )
        self.monitor_process.start()

    def stop(self):
        """Closes queue and waits for resource monitor to finish."""
        with open(self.pid_file, 'w') as fhandle:
            fhandle.write('exit')
        self.queue.close()
        self.queue.join_thread()
        self.monitor_process.join()
        self.remove_pid_file()


class _ModuleImporter(object):
    """A private class that imports a particular models and return boolean
    variable indicating if import has been succesfull or not. Used by a Modules
    class to identify if optional python modules are available.
    """
    @staticmethod
    def try_import(module_name):
        """Tries to import module.

        :param str module_name: A name of a module to try to import, something like
                                'numpy', 'pandas', 'matplotlib' etc.
        :return: True if module has been imported, False otherwise.
        """
        have_module = True
        try:
            importlib.import_module(module_name)
        except ImportError:
            logging.warn("Module '%s' cannot be imported, certain system information will not be available", module_name)
            have_module = False
        return have_module


class Modules(object):
    """A class that enumerates non-standard python modules this project depends on.
    They are optional, so we can disable certain functionality if something is missing.
    """
    HAVE_NUMPY = _ModuleImporter.try_import('numpy')
    HAVE_PANDAS = _ModuleImporter.try_import('pandas')
    HAVE_MATPLOTLIB = _ModuleImporter.try_import('matplotlib')
