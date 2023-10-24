mitol-django-geoip
---

`geoip` provides IP geolocation services. At its core, it allows you to pass a 
client's IP address to it, and it will send you back a good estimation of what
country the client belongs to. 

Specifically, this wraps lookup around using a _local_ copy of the MaxMind 
GeoIP2 data. This choice was made to avoid having to hit an API during checkout
operations, where doing so may end up blocking the client for an unknown amount
of time. 

The `geoip` app provides lookup for a user's country code only so, while you can
use datasets that contain more granular location data in them, you'll still only
get back the country ISO code from the API in this app. 

### Setup

You will need a copy of the MaxMind GeoIP2 data in CSV format. This is provided
in several ways:

* For most purposes, the **GeoLite2** dataset is the recommended option. This option provides less features but the dataset is available for free. 
* The paid **GeoIP2** dataset can also be used with this library. 

In both cases, you will need the CSV format versions of the databases. The Lite
version is available in ASN, City and Country versions; choose between the City 
and Country versions. (The ASN database is not used nor supported.) If the
dataset is only to be used with this app, the Country version is sufficient and
also the smallest. 

The downloaded datasets include the network block information in two CSV files -
one each for IPv4 and IPv6 network blocks - and the location data in a variety 
of languages. The English language `en` one is required by the app but you can
import any others that you require.

After installing the app into your Django project in the normal way, you should
have a management command called `import_maxmind_data` available to you. Run 
this command to import the data from the CSV file you downloaded. You _have_ to
import the IPv4 netblock file and the English langauge location file but it is
recommended to also import the IPv6 netblock file. 

#### Working Locally

If you're working locally, the API will never return a country code. The MaxMind
datasets don't include the private network blocks in them as they don't really 
map to anything, so there's no match for any of the private network IPs. 

If you'd like these IPs to match something, you can add that data by running the
`create_private_maxmind_data` command. This will create a fake location record
and netblock records for the 3 private network blocks available: 
* 10.0.0.0/24 
* 172.16.0.0/20 _(172.16.0.0-172.31.255.255)_
* 192.168.0.0/16

You can specify what ISO code you wish to assign to these as well. Running the 
command again will allow you to re-assign the ISO code. 

Note that there is no IPv6 block specified because there are no private IPv6
network addresses (in the same way that there are IPv4 ones).

### Usage

Import `ip_to_country_code` from `api` and call it with the IP address you've 
collected from the client. This will return the ISO 3166 alpha2 country code
that the IP belongs to, or None if there isn't one. (See note under Working 
Locally above for important information about private IPv4 network blocks.)

### Updating

MaxMind updates the GeoIP2 and GeoLite2 datasets on a regular schedule. You can
update the databases by rerunning the `import_maxmind_data` using newly
downloaded copies of the dataset. 

MaxMind does provide a method for downloading the dataset programmatically - in
the downloads section in your account, you can click Get Permalink for the
data files you want. You can then update the link with your API key and write a
task to download and then ingest the files. If you're writing this as a task
from within your Django app (i.e. a Celery task), you can directly call the
`import_maxmind_database` to do the heavy lifting once the dataset is
downloaded. See the MaxMind developer portal to find the dates when the datasets
are refreshed.

The import command is idempotent.

### Caveats

Note that IP blocks may be reassigned or otherwise move between places for any
reason, so the location that is resolved using a specific IP at one point in
time may resolve to a different location in the future. You should design your
app to store the resolved country code at the time of query if you need to
refer to that data later.
