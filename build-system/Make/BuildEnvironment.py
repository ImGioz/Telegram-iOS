import json
import os
import platform
import subprocess


def is_apple_silicon():
    if platform.processor() == 'arm':
        return True
    else:
        return False


def get_clean_env():
    clean_env = os.environ.copy()
    clean_env['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
    return clean_env


def resolve_executable(program):
    def is_executable(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    for path in get_clean_env()["PATH"].split(os.pathsep):
        executable_file = os.path.join(path, program)
        if is_executable(executable_file):
            return executable_file
    return None


def run_executable_with_output(path, arguments):
    executable_path = resolve_executable(path)
    if executable_path is None:
        raise Exception('Could not resolve {} to a valid executable file'.format(path))

    process = subprocess.Popen(
        [executable_path] + arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=get_clean_env()
    )
    output_data, _ = process.communicate()
    output_string = output_data.decode('utf-8')
    return output_string


def call_executable(arguments, use_clean_environment=True, check_result=True):
    executable_path = resolve_executable(arguments[0])
    if executable_path is None:
        raise Exception('Could not resolve {} to a valid executable file'.format(arguments[0]))

    if use_clean_environment:
        resolved_env = get_clean_env()
    else:
        resolved_env = os.environ

    resolved_arguments = [executable_path] + arguments[1:]

    if check_result:
        subprocess.check_call(resolved_arguments, env=resolved_env)
    else:
        subprocess.call(resolved_arguments, env=resolved_env)


def get_bazel_version(bazel_path):
    command_result = run_executable_with_output(bazel_path, ['--version']).strip('\n')
    if not command_result.startswith('bazel '):
        raise Exception('{} is not a valid bazel binary'.format(bazel_path))
    command_result = command_result.replace('bazel ', '')
    return command_result


def get_xcode_version():
    xcode_path = run_executable_with_output('xcode-select', ['-p']).strip('\n')
    if not os.path.isdir(xcode_path):
        print('The path reported by \'xcode-select -p\' does not exist')
        exit(1)

    plist_path = '{}/../Info.plist'.format(xcode_path)

    info_plist_lines = run_executable_with_output('plutil', [
        '-p', plist_path
    ]).split('\n')

    pattern = 'CFBundleShortVersionString" => '
    for line in info_plist_lines:
        index = line.find(pattern)
        if index != -1:
            version = line[index + len(pattern):].strip('"')
            return version

    print('Could not parse the Xcode version from {}'.format(plist_path))
    exit(1)


class BuildEnvironment:
    def __init__(
            self,
            base_path,
            bazel_path,
            bazel_x86_64_path,
            override_bazel_version,
            override_xcode_version
            ):
        self.base_path = os.path.expanduser(base_path)
        self.bazel_path = os.path.expanduser(bazel_path)
        if bazel_x86_64_path is not None:
            self.bazel_x86_64_path = os.path.expanduser(bazel_x86_64_path)
        else:
            self.bazel_x86_64_path = None

        configuration_path = os.path.join(self.base_path, 'versions.json')
        with open(configuration_path) as file:
            configuration_dict = json.load(file)
            if configuration_dict['app'] is None:
                raise Exception('Missing app version in {}'.format(configuration_path))
            else:
                self.app_version = configuration_dict['app']
            if configuration_dict['bazel'] is None:
                raise Exception('Missing bazel version in {}'.format(configuration_path))
            else:
                self.bazel_version = configuration_dict['bazel']
            if configuration_dict['xcode'] is None:
                raise Exception('Missing xcode version in {}'.format(configuration_path))
            else:
                self.xcode_version = configuration_dict['xcode']

        actual_bazel_version = get_bazel_version(self.bazel_path)
        if actual_bazel_version != self.bazel_version:
            if override_bazel_version:
                print('Overriding the required bazel version {} with {} as reported by {}'.format(
                    self.bazel_version, actual_bazel_version, self.bazel_path))
                self.bazel_version = actual_bazel_version
            else:
                print('Required bazel version is "{}", but "{}"" is reported by {}'.format(
                    self.bazel_version, actual_bazel_version, self.bazel_path))
                exit(1)

        actual_xcode_version = get_xcode_version()
        if actual_xcode_version != self.xcode_version:
            if override_xcode_version:
                print('Overriding the required Xcode version {} with {} as reported by \'xcode-select -p\''.format(
                    self.xcode_version, actual_xcode_version, self.bazel_path))
                self.xcode_version = actual_xcode_version
            else:
                print('Required Xcode version is {}, but {} is reported by \'xcode-select -p\''.format(
                    self.xcode_version, actual_xcode_version, self.bazel_path))
                exit(1)
