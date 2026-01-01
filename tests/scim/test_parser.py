import pytest
from faker import Faker
from mitol.scim.parser import Filters

faker = Faker()


def test_scim_filter_parser():
    """Runer the parser tests"""
    success, _results = Filters.run_tests(
        """\
        userName eq "bjensen"

        name.familyName co "O'Malley"

        userName sw "J"

        urn:ietf:params:scim:schemas:core:2.0:User:userName sw "J"

        title pr

        meta.lastModified gt "2011-05-13T04:42:34Z"

        meta.lastModified ge "2011-05-13T04:42:34Z"

        meta.lastModified lt "2011-05-13T04:42:34Z"

        meta.lastModified le "2011-05-13T04:42:34Z"

        title pr and userType eq "Employee"

        title pr or userType eq "Intern"

        schemas eq "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"

        userType eq "Employee" and (emails co "example.com" or emails.value co "example.org")

        userType ne "Employee" and not (emails co "example.com" or emails.value co "example.org")

        userType eq "Employee" and (emails.type eq "work")

        userType eq "Employee" and emails[type eq "work" and value co "@example.com"]

        emails[type eq "work" and value co "@example.com"] or ims[type eq "xmpp" and value co "@foo.com"]
        """  # noqa: E501
    )

    # run_tests will output error messages
    assert success


@pytest.mark.parametrize("count", [10, 100, 1000, 5000])
def test_large_filter(count):
    """Test that the parser can handle large filters"""

    filter_str = " OR ".join(
        [f'email.value eq "{faker.email()}"' for _ in range(count)]
    )

    success, _ = Filters.run_tests(filter_str)

    # run_tests will output error messages
    assert success
