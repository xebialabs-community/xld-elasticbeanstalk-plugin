#
# Copyright 2019 XEBIALABS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#


from elasticbeanstalk import create_session
from elasticbeanstalk.array_utils import ArrayUtil as arr
from boto3.session import Session
import time


class EBClient(object):
    def __init__(self, access_key, access_secret, eb_app_env):
        self.eb_app_env = eb_app_env
        self.session = Session(aws_access_key_id=access_key,
                               aws_secret_access_key=access_secret,
                               botocore_session=create_session())
        self.eb_client = self.session.client('elasticbeanstalk', region_name=eb_app_env.region)
        self.s3_client = self.session.client('s3', region_name=eb_app_env.region)

    @staticmethod
    def new_instance(eb_app_env_ci):
        return EBClient(eb_app_env_ci.account.accesskey, eb_app_env_ci.account.accessSecret, eb_app_env_ci)

    def application_exists(self):
        applications = self.eb_client.describe_applications()['Applications']
        return arr.find_by_attr(applications, 'ApplicationName', self.eb_app_env.application_name) is not None

    def create_application(self):
        if not self.application_exists():
            self.eb_client.create_application(ApplicationName=self.eb_app_env.application_name)
            return True
        return False

    def delete_application(self, wait=True, sleep_interval=5):
        if self.application_exists():
            self.eb_client.delete_application(ApplicationName=self.eb_app_env.application_name,
                                              TerminateEnvByForce=True)
            while self.application_exists() and wait:
                time.sleep(sleep_interval)
            return True
        return False

    def env_exists(self):
        envs = self.eb_client.describe_environments(ApplicationName=self.eb_app_env.application_name)['Environments']
        envs = [e for e in envs if e["Status"] != "Terminated" and e["Status"] != "Terminating"]
        return arr.find_by_attr(envs, 'EnvironmentName', self.eb_app_env.environment_name) is not None

    def get_env_by_id(self, environment_id):
        result = self.eb_client.describe_environments(ApplicationName=self.eb_app_env.application_name,
                                                      EnvironmentIds=[environment_id])
        result_size = len(result['Environments'])
        if result_size != 1:
            raise Exception("Environment '%s' not found for Application '%s'. Instances found %s" %
                            (self.eb_app_env.environment_name, self.eb_app_env.application_name, result_size))
        return result['Environments'][0]

    def get_active_env(self):
        result = self.eb_client.describe_environments(ApplicationName=self.eb_app_env.application_name,
                                                      EnvironmentNames=[self.eb_app_env.environment_name])
        envs = [e for e in result['Environments'] if e["Status"] != "Terminated"]
        result_size = len(envs)
        if result_size != 1:
            raise Exception("Environment '%s' not found for Application '%s'. Instances found %s" %
                            (self.eb_app_env.environment_name, self.eb_app_env.application_name, result_size))
        return envs[0]

    def log_events(self, env_id, event_log):
        response = self.eb_client.describe_events(ApplicationName=self.eb_app_env.application_name,
                                                  EnvironmentId=env_id)
        events = sorted(response["Events"], key=lambda x: x["EventDate"])
        for e in events:
            if e["EventDate"] not in event_log:
                event_log.append(e["EventDate"])
                print "%s: %s" % (e["EventDate"], e["Message"])
        return event_log

    def wait_for_env_ready_status(self, env_id, sleep_interval=5):
        ready_statuses = ['Ready']
        stopped_statuses = ['Terminated']
        wait_statuses = ['Launching', 'Updating', 'Terminating']
        event_log = []
        while True:
            self.log_events(env_id, event_log)
            env_status = self.get_env_by_id(env_id)['Status']
            if env_status in ready_statuses:
                return True
            elif env_status in stopped_statuses:
                raise Exception("Expected environment [%s] to be in 'Ready' state, but was 'Terminated'" % env_id)
            elif env_status in wait_statuses:
                time.sleep(sleep_interval)
            else:
                raise Exception("Unknown environment status '%s'" % env_status)

    def wait_for_env_terminated_status(self, env_id, sleep_interval=5):
        stopped_statuses = ['Terminated']
        wait_statuses = ['Ready', 'Launching', 'Updating', 'Terminating']
        event_log = []
        while True:
            self.log_events(env_id, event_log)
            env_status = self.get_env_by_id(env_id)['Status']
            if env_status in stopped_statuses:
                return True
            elif env_status in wait_statuses:
                time.sleep(sleep_interval)
            else:
                raise Exception("Unknown environment status '%s'" % env_status)

    def validate_solution_stack_name(self):
        stacks = self.eb_client.list_available_solution_stacks()['SolutionStacks']
        arr.must_find(stacks, self.eb_app_env.solution_stack_name)

    def prepare_options(self, env_vars):
        # http://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html#command-options-general-ec2vpc
        options = []

        def add_option(ns, name, value):
            if value is not None and len(value.strip()) > 0:
                options.append({"Namespace": ns, "OptionName": name, "Value": value})

        o = self.eb_app_env
        add_option("aws:autoscaling:launchconfiguration", "IamInstanceProfile", o.iamInstanceProfile)
        add_option("aws:autoscaling:launchconfiguration", "InstanceType", o.instanceType)
        add_option("aws:autoscaling:updatepolicy:rollingupdate", "RollingUpdateType", o.rollingUpdateType)
        add_option("aws:autoscaling:updatepolicy:rollingupdate", "RollingUpdateEnabled", o.rollingUpdateEnabled)
        add_option("aws:elasticbeanstalk:command", "BatchSize", o.batchSize)
        add_option("aws:elasticbeanstalk:command", "BatchSizeType", o.batchSizeType)
        add_option("aws:elasticbeanstalk:environment", "ServiceRole", o.serviceRole)
        add_option("aws:elasticbeanstalk:healthreporting:system", "SystemType", o.systemType)
        add_option("aws:elb:loadbalancer", "CrossZone", o.crossZone)
        add_option("aws:elb:policies", "ConnectionDrainingEnabled", o.connectionDrainingEnabled)

        add_option("aws:ec2:vpc", "VPCId", o.vpcId)
        add_option("aws:ec2:vpc", "Subnets", o.subnets)
        add_option("aws:ec2:vpc", "ELBSubnets", o.elbSubnets)
        add_option("aws:ec2:vpc", "ELBScheme", o.elbScheme)
        add_option("aws:ec2:vpc", "DBSubnets", o.dbSubnets)
        add_option("aws:ec2:vpc", "AssociatePublicIpAddress", o.associatePublicIpAddress)

        if len(env_vars.keys()) > 0:
            for k, v in env_vars.items():
                add_option("aws:elasticbeanstalk:application:environment", k, v)
        return options

    @staticmethod
    def not_empty(value):
        return value is not None and len(value.strip()) > 0

    def prepare_env_details(self, env_vars, is_update=False):
        def add_detail(name, value, target):
            if self.not_empty(value):
                target[name] = value

        o = self.eb_app_env
        details = {}
        add_detail("ApplicationName", o.application_name, details)
        add_detail("EnvironmentName", o.environment_name, details)
        self.validate_solution_stack_name()
        add_detail("Description", o.description, details)
        add_detail("SolutionStackName", o.solution_stack_name, details)
        add_detail("CNAMEPrefix", o.cname_prefix, details)

        if self.not_empty(o.tier_name) or self.not_empty(o.tier_type) or self.not_empty(o.tier_version):
            tier = {}
            add_detail("Name", o.tier_name, tier)
            add_detail("Type", o.tier_type, tier)
            add_detail("Version", o.tier_version, tier)
            details["Tier"] = tier

        if not is_update:
            tags = []
            for k, v in o.env_tags.items():
                tags.append({"Key": k, "Value": v})
            details["Tags"] = tags
        details["OptionSettings"] = self.prepare_options(env_vars)
        return details

    def delete_env(self, wait=True, sleep_interval=5):
        if self.env_exists():
            env_details = self.get_active_env()
            self.eb_client.terminate_environment(EnvironmentId=env_details['EnvironmentId'],
                                                 TerminateResources=True,
                                                 ForceTerminate=True)
            if wait:
                self.wait_for_env_terminated_status(env_details['EnvironmentId'], sleep_interval=sleep_interval)
            return True
        return False

    def bucket_exists(self):
        buckets = self.s3_client.list_buckets()["Buckets"]
        return arr.find_by_attr(buckets, 'Name', self.eb_app_env.s3_bucket_name) is not None

    def create_bucket_if_needed(self):
        if not self.bucket_exists():
            self.s3_client.create_bucket(ACL='private', Bucket=self.eb_app_env.s3_bucket_name,
                                         CreateBucketConfiguration={'LocationConstraint': self.eb_app_env.region})

    def delete_bucket(self):
        if self.bucket_exists():
            self.s3_client.delete_bucket(Bucket=self.eb_app_env.s3_bucket_name)

    def upload_artifact(self, name, version, source_file_path):
        target_name = self.create_target_file_name(name, version)
        self.create_bucket_if_needed()
        response = self.s3_client.list_objects(Bucket=self.eb_app_env.s3_bucket_name)
        if "Contents" in response.keys():
            contents = response["Contents"]
        else:
            contents = []
        if not arr.find_by_attr(contents, 'Key', target_name):
            with open(source_file_path, 'rb') as data:
                self.s3_client.put_object(Bucket=self.eb_app_env.s3_bucket_name, Key=target_name, Body=data)
            return True
        return False

    @staticmethod
    def create_target_file_name(name, version):
        name = name.replace(" ", "_")
        target_name = "%s-%s.zip" % (name, version)
        return target_name

    def delete_artifact(self, name, version):
        target_name = self.create_target_file_name(name, version)
        contents = self.s3_client.list_objects(Bucket=self.eb_app_env.s3_bucket_name)["Contents"]
        if arr.find_by_attr(contents, 'Key', target_name):
            self.s3_client.delete_object(Bucket=self.eb_app_env.s3_bucket_name, Key=target_name)
            return True
        return False

    def application_version_exists(self, version):
        application_versions = self.eb_client.describe_application_versions(
            ApplicationName=self.eb_app_env.application_name)['ApplicationVersions']
        return arr.find_by_attr(application_versions, 'VersionLabel', version) is not None

    def get_application_version(self, version_label):
        result = self.eb_client.describe_application_versions(ApplicationName=self.eb_app_env.application_name,
                                                              VersionLabels=[version_label])
        versions = result["ApplicationVersions"]
        result_size = len(versions)
        if result_size != 1:
            raise Exception("Application version '%s' not found for Application '%s'. Instances found %s" %
                            (version_label, self.eb_app_env.application_name, result_size))
        return versions[0]

    def wait_for_application_version_proccessed_status(self, version_label, sleep_interval=5):
        ready_statuses = ['processed', 'unprocessed']
        stopped_statuses = ['failed']
        wait_statuses = ['processing', 'building']
        while True:
            version_status = self.get_application_version(version_label)['Status'].lower()
            if version_status in ready_statuses:
                return True
            elif version_status in stopped_statuses:
                raise Exception("Expected application version [%s] to be in 'Processed' state, but was '%s'"
                                % (version_label, version_status))
            elif version_status in wait_statuses:
                time.sleep(sleep_interval)
            else:
                raise Exception("Unknown application version status '%s'" % version_status)

    @staticmethod
    def version_label(name, version):
        return "%s-%s" % (name, version)

    def create_application_version(self, name, version, wait=True, sleep_interval=5):
        version_label = self.version_label(name, version)
        created = False
        target_file = self.create_target_file_name(name, version)
        if not self.application_version_exists(version_label):
            self.eb_client.create_application_version(
                                    ApplicationName=self.eb_app_env.application_name,
                                    VersionLabel=version_label,
                                    SourceBundle={
                                        'S3Bucket': self.eb_app_env.s3_bucket_name,
                                        'S3Key': target_file
                                    })
            created = True
        else:
            self.get_application_version(version_label)

        if wait:
            self.wait_for_application_version_proccessed_status(version_label, sleep_interval=sleep_interval)
        return [created, version_label]

    def deploy_application_version(self, version_label, env_vars, wait=True, sleep_interval=5):
        env_exists = self.env_exists()
        args = self.prepare_env_details(env_vars, is_update=env_exists)
        args["VersionLabel"] = version_label

        if env_exists:
            env_details = self.eb_client.update_environment(**args)
        else:
            env_details = self.eb_client.create_environment(**args)

        if wait:
            self.wait_for_env_ready_status(env_details['EnvironmentId'], sleep_interval=sleep_interval)
        return env_details






