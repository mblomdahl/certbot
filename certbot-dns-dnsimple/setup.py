from distutils.version import LooseVersion
import os
import sys

from setuptools import __version__ as setuptools_version
from setuptools import find_packages
from setuptools import setup

version = '1.10.1'

# Remember to update local-oldest-requirements.txt when changing the minimum
# acme/certbot version.
install_requires = [
    'setuptools',
    'zope.interface',
]

if not os.environ.get('SNAP_BUILD'):
    install_requires.extend([
        'acme>=0.31.0',
        'certbot>=1.1.0',
    ])
elif 'bdist_wheel' in sys.argv[1:]:
    raise RuntimeError('Unset SNAP_BUILD when building wheels '
                       'to include certbot dependencies.')
if os.environ.get('SNAP_BUILD'):
    install_requires.append('packaging')

setuptools_known_environment_markers = (LooseVersion(setuptools_version) >= LooseVersion('36.2'))
if setuptools_known_environment_markers:
    install_requires.append('mock ; python_version < "3.3"')
elif 'bdist_wheel' in sys.argv[1:]:
    raise RuntimeError('Error, you are trying to build certbot wheels using an old version '
                       'of setuptools. Version 36.2+ of setuptools is required.')
elif sys.version_info < (3,3):
    install_requires.append('mock')

# This package normally depends on dns-lexicon>=3.2.1 to address the
# problem described in https://github.com/AnalogJ/lexicon/issues/387,
# however, the fix there has been backported to older versions of
# lexicon found in various Linux distros. This conditional helps us test
# that we've maintained compatibility with these versions of lexicon
# which allows us to potentially upgrade our packages in these distros
# as necessary.
if os.environ.get('CERTBOT_OLDEST') == '1':
    install_requires.append('dns-lexicon>=2.2.1')
else:
    install_requires.append('dns-lexicon>=3.2.1')

docs_extras = [
    'Sphinx>=1.0',  # autodoc_member_order = 'bysource', autodoc_default_flags
    'sphinx_rtd_theme',
]

setup(
    name='certbot-dns-dnsimple',
    version=version,
    description="DNSimple DNS Authenticator plugin for Certbot",
    url='https://github.com/certbot/certbot',
    author="Certbot Project",
    author_email='client-dev@letsencrypt.org',
    license='Apache License 2.0',
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Plugins',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Security',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Networking',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],

    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    extras_require={
        'docs': docs_extras,
    },
    entry_points={
        'certbot.plugins': [
            'dns-dnsimple = certbot_dns_dnsimple._internal.dns_dnsimple:Authenticator',
        ],
    },
)
