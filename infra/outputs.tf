output "cloudfront_url" {
  description = "Public HTTPS URL for the Sentinel UI (and /api/* proxy)"
  value       = "https://${aws_cloudfront_distribution.cdn.domain_name}"
}

output "ec2_public_ip" {
  description = "Direct EC2 public IP — useful for SSH debugging"
  value       = aws_instance.api.public_ip
}

output "ec2_public_dns" {
  description = "EC2 public DNS hostname"
  value       = aws_instance.api.public_dns
}

output "s3_frontend_bucket" {
  description = "S3 bucket name — use with: aws s3 sync dist/ s3://<bucket>"
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID — needed to invalidate cache after deploy"
  value       = aws_cloudfront_distribution.cdn.id
}
