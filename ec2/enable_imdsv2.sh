#!/bin/bash
input="./instances"
export AWS_PAGER="" 

######################################
# $IFS removed to allow the trimming # 
#####################################
while read -r line
do
  echo "$line"
  aws ec2 modify-instance-metadata-options \
    --instance-id $line \
    --http-tokens required \
    --http-endpoint enabled
done < "$input"

