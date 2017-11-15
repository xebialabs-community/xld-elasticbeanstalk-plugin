#
# Copyright 2017 XEBIALABS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#


from elasticbeanstalk.eb_client import EBClient


def process(deployment_vars):
    deployed = deployment_vars['deployed']
    container = deployed.container
    client = EBClient.new_instance(container)
    print "Ensure ElasticBeanstalk application '%s' present." % container.application_name
    if client.create_application():
        print "ElasticBeanstalk application created successfully."
    target_name = client.create_target_file_name(deployed.name, deployed.bundle_version)
    print "Upload artifact '%s' to bucket '%s'" % (target_name, container.s3_bucket_name)
    uploaded = client.upload_artifact(deployed.name, deployed.bundle_version, deployed.file.path)
    if not uploaded:
        print "Artifact already exists in bucket. Will not upload again."
    version_label = client.version_label(deployed.name, deployed.bundle_version)
    print "Ensure ElasticBeanstalk version '%s' present." % version_label
    created, version_label = client.create_application_version(deployed.name, deployed.bundle_version)
    if created:
        print "ElasticBeanstalk version created successfully"
    print "Deploying version '%s' to environment '%s'" % (version_label, container.environment_name)
    client.deploy_application_version(version_label, deployed.env_vars)
    print "Done"


if __name__ == '__main__' or __name__ == '__builtin__':
    process(locals())
