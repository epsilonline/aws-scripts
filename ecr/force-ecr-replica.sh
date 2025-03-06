#!/bin/bash

"""
If you enable ecr replica, when push new images, ecr replicate image in another registry.
Existing images are not replicated, for force this replica you can:
1. pull image from primary registry
2. delete image from primary registry
3. push image on primary registry

This script automate this process for all registry in one region
"""

IMAGE_TAG="latest"
SLEEP_TIME="0.5"

function usage() {
   echo "Force ecr replica for existing images in specified region."
   echo "This script not configure replica."
   echo
   echo "Syntax: force-ecr-replica.sh -r SOURCE_REGION [t|h]"
   echo "options:"
   echo " r: ECR source region. Required."
   echo " t: Image tag to replicate. Default is latest."
   echo " h: Print this Help."
   echo
   exit 0
}

while getopts r:t:h: flag
do
    case "${flag}" in
        r) REGION=${OPTARG};;
        t) IMAGE_TAG=${OPTARG};;
        h) usage;;
        *);;
    esac
done

if [ -z "${REGION}" ]; then
  usage ;
fi


REPOSITORY_URIS=$(aws ecr describe-repositories --query "repositories[*].repositoryUri" --output text)

# login on registry
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
REGISTRY_URL="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "Login to ${REGISTRY_URL}"
aws ecr get-login-password | docker login --username AWS --password-stdin "${REGISTRY_URL}"

for REPOSITORY_URI in ${REPOSITORY_URIS}
do
    ECR_NAME="${REPOSITORY_URI##*/}"
    IMAGE="${REPOSITORY_URI}:${IMAGE_TAG}"
    echo "Force replica for image: ${IMAGE}"
    docker pull "${IMAGE}"
    aws ecr batch-delete-image --repository-name "${ECR_NAME}" --image-ids imageTag="${IMAGE_TAG}" --output text --no-cli-pager
    sleep ${SLEEP_TIME}
    docker push "${IMAGE}"
    docker rmi "${IMAGE}"
    sleep ${SLEEP_TIME}
done