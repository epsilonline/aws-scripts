# CLOUDFRONT

## Descriptions

Helper script for AWS Cloudfront.

## Available commands

- **update-cdn-with-json**: change origin on cloudfront distribution 
- **update-all-cdns**: change origin for implement dr strategy in ***REMOVED***, AKA switch region

## Usage
```Bash
python3 main.py --help
```

### update-cdn-with-json

1) Create a json file named `distributions.json`, fill it with configurations. You can take `sample_distributions.json` as exemple file to use.
2) Once the json file has been created run:
```
 aws-scripts cloudfront update-cdn-with-json <aws profile> <aws region>
```

### update-all-cdns
For all Cloudfront distribution replace all origin using this logic:
- **S3**: get backup url, remove region and additional info such as random id at end of name and search bucket with simil name in other region and update
- **ALB**: Replace alb value with input parameter
- **WAF**: Replace centralized waf with the maintenance one

### revert-update-all-cdns
For all Cloudfront distribution revert changes done by update-all-cdns command:
- **S3**: get backup url, remove region and additional info such as random id at end of name and search bucket with simil name in other region and update
- **ALB**: Replace alb value with input parameter
- **WAF**: Replace maintenance waf with the centralized one

### update-all-cdns-tls-version
All Cloudfront distribution tls version will be replaced with the provided one:
```
aws-scripts cloudfront update-all-cdns-tls-version <aws profile> <tls version>
```