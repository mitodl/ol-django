mitol-django-geoip
---

`geoip` provides IP geolocation services. At its core, it allows you to pass a 
client's IP address to it, and it will send you back a good estimation of what
country the client belongs to. 

Specifically, this wraps lookup around using a _local_ copy of the MaxMind 
GeoIP2/GeoLite2 data. This choice was made to avoid having to hit an API during
checkout operations, where doing so may end up blocking the client for an 
unknown amount of time. 

The `geoip` app provides lookup for a user's country code only so, while you can
use datasets that contain more granular location data in them, you'll still only
get back the country ISO code from the API in this app. 

### Setup

The MaxMind geolocation databases are provided in two forms:

* The **GeoLite2** database is free.
* The **GeoIP2** database is not free - a subscription fee applies. 

Which one you need will depend on your use case - however, if your intent is
only to use the dataset with this app, the **GeoLite2** database is sufficient.

In both cases, you will need the CSV format versions of the databases. You have 
the option of downloading the ASN, City, or Country versions of the database.
For the purposes of this app, the Country version is sufficient; if you plan on
using the MaxMind data elsewhere in your project and need more granular location
data, you can use the City version instead. The ASN database is not supported
and can be skipped unless you have a specific need for it.

The downloaded datasets include the network block information in two CSV files -
one each for IPv4 and IPv6 network blocks - and the location data in a variety 
of languages. The English language `en` one is required by the app but you can
import any others that you require.

After installing the app into your Django project in the normal way, you should
have a management command called `import_maxmind_data` available to you. Run 
this command to import the data from the CSV file you downloaded. You _must_
import the IPv4 netblock file and the English langauge location file but it is
recommended to import the IPv6 netblock file as well, especially if your app
will be capable of serving IPv6 clients.  

#### Working Locally

If you're working locally, the API will never return a country code. The MaxMind
datasets don't include the private network blocks in them as they don't really 
map to anything, so there's no match for any of the private network IPs. 

If you'd like these IPs to match something, you can add that data by running the
`create_private_maxmind_data` command. This will create a set of fake netblock 
records for the 3 private network blocks available: 
* 10.0.0.0/24 
* 172.16.0.0/12 _(172.16.0.0-172.31.255.255)_
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
