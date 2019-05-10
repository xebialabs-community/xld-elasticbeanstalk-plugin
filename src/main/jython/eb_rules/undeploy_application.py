#
# Copyright 2019 XEBIALABS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#


from elasticbeanstalk.eb_client import EBClient


def process(deployment_vars):
    deployed = deployment_vars['previousDeployed']
    container = deployed.container
    client = EBClient.new_instance(container)
    bv = deployed.bundle_version
    bundle_version = bv if client.not_empty(bv) else deployment_vars["appVersion"]
    version_label = client.version_label(deployed.name, bundle_version)
    print "Undeploying version '%s' from environment '%s'" % (version_label, container.environment_name)
    if client.delete_env():
        print "Application and environment destroyed."
    else:
        print "Environment '%s' does not exist. Ignoring." % container.environment_name
    print "Done"


if __name__ == '__main__' or __name__ == '__builtin__':
    process(locals())
