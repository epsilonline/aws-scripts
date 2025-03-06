#!/bin/bash

HELP="""Required arguments:\n
- p\t\tAWS profile\n
- e\t\tEnvironment (if set to 'all', no check on the environment will be performed)\n\n
Optional arguments:\n
- i\t\tPrint GP2 volumes info only, without performing migration\n\n
"""

while getopts "p:e:i:h" flag
do
    case "${flag}" in
        p) AWS_PROFILE=${OPTARG};;
        e) ENV=${OPTARG};;
		i) PRINT_CSV=${OPTARG};;
        h) echo -e ${HELP}
		exit 0;;
    esac
done

get_volumes() {
	aws ec2 describe-volumes \
	--filters Name=volume-type,Values=gp2 \
	--profile $AWS_PROFILE \
	| jq -r '.Volumes[] | "\(.VolumeId);\(.Iops);\(.Attachments[].InstanceId)"' \
	> ./volumes.csv

	if [[ $PRINT_CSV == true ]]; then
		echo "----------------------------------------------"
		printf "\tVOLUME_ID     IOPS      INSTANCE_ID\n"
		echo "----------------------------------------------"
		cat ./volumes.csv
		exit 0
	fi
}

get_instance_env() {
	aws ec2 describe-instances \
	--profile $AWS_PROFILE \
	--instance-ids $INSTANCE_ID \
	--query "Reservations[*].Instances[*].Tags[?Key == 'Environment'].Value" --output json | jq -r ".[0]" | jq -r ".[0]" | jq -r ".[0]" | awk '{print tolower($0)}'
}

migrate() {
	if [[ $IOPS < 3000 ]]; then
		printf "\nMigrating\n"
		aws ec2 modify-volume --volume-type gp3 --volume-id $VOLUME_ID --no-cli-pager --profile $AWS_PROFILE
	else
		printf "\nMigrating with IOPS > 3000\n"
		aws ec2 modify-volume --volume-type gp3 --volume-id $VOLUME_ID --iops $IOPS --no-cli-pager --profile $AWS_PROFILE
	fi
}

main() {
	if [[ $ENV == "all" ]]; then
		while IFS=";" read -r VOLUME_ID IOPS INSTANCE_ID
		do
			printf "\nID: $VOLUME_ID, IOPS: $IOPS, InstanceID: $INSTANCE_ID"
			migrate;
		done < volumes.csv
	else
		while IFS=";" read -r VOLUME_ID IOPS INSTANCE_ID
		do
			printf "\nID: $VOLUME_ID, IOPS: $IOPS, InstanceID: $INSTANCE_ID"

			EC2_ENV=$(get_instance_env)
			if [[ $EC2_ENV == $ENV ]]; then
				migrate;
			else
				printf "\nSkipped because EC2 instance belongs to $EC2_ENV environment\n"
			fi
		done < volumes.csv		
	fi
}

get_volumes;
main;