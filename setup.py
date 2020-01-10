import os
from setuptools import find_packages, setup
import versioneer

commands = versioneer.get_cmdclass().copy()

pkgname = 'psyncd'


def package_files(directories):
    if isinstance(directories, str):
        directories = [directories]
    paths = []
    for directory in directories:
        for (path, directories, filenames) in os.walk(directory):
            for filename in filenames:
                paths.append(os.path.join('..', path, filename))
    return paths



# Currently using symlinks to make directory structure look more like a package
# since package_dir is not behaving properly with pip -e.
packages = find_packages()
print('Packages:', packages)

# common dependencies
# todo: fully test unified dependencies
deps = [
    'appdirs~=1.4',
    'inotify~=0.2.10',
    'typing',
    'pyyaml',

]

setup(
    name=pkgname,
    version=versioneer.get_version(),
    script_name='setup.py',
    python_requires='>3.5',
    zip_safe=False,
    packages=packages,
    install_requires=deps,
    include_package_data=True,
    extras_require={},
    cmdclass=commands,
    scripts=['psyncd/scripts/psyncd']
)
