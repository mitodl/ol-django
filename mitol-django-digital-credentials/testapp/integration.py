"""Integration test code"""


def build_credential(courseware_object, learner_did):  # pylint: disable=unused-argument
    """Test func for building credentials"""
    return {
        "credential": {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://www.w3.org/2018/credentials/examples/v1",
            ],
            "id": "http://example.gov/credentials/3732",
            "type": ["VerifiableCredential", "UniversityDegreeCredential"],
            "issuer": "did:web:digitalcredentials.github.io",
            "issuanceDate": "2020-03-10T04:24:12.164Z",
            "credentialSubject": {
                "type": "Person",
                "id": learner_did.did,
                "name": f"{learner_did.learner.first_name} {learner_did.learner.last_name}",
                "degree": {
                    "type": "BachelorDegree",
                    "name": "Bachelor of Science and Arts",
                },
            },
        },
        "options": {
            "verificationMethod": "did:web:digitalcredentials.github.io#96K4BSIWAkhcclKssb8yTWMQSz4QzPWBy-JsAFlwoIs"
        },
    }
