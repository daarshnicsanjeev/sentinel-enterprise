output "s3_website_url" {
  description = "Public URL of the React frontend (S3 static website endpoint)"
  value       = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
}

output "ec2_public_ip" {
  description = "Public IPv4 address of the FastAPI backend EC2 instance"
  value       = aws_instance.sentinel_api.public_ip
}

output "ec2_api_url" {
  description = "Direct URL to the FastAPI backend"
  value       = "http://${aws_instance.sentinel_api.public_ip}:8000"
}

output "ssh_command" {
  description = "SSH command to connect to the EC2 instance (replace key path as needed)"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_instance.sentinel_api.public_ip}"
}

output "deploy_frontend_command" {
  description = "AWS CLI command to upload the React build to S3"
  value       = "aws s3 sync frontend/sentinel-ui/dist/ s3://${var.frontend_bucket_name} --delete"
}

output "cloudfront_url" {
  description = "HTTPS URL of the React frontend via CloudFront"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}
