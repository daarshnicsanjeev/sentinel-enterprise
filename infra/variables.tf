variable "aws_region" {
  description = "AWS region — ap-south-1 is Mumbai (closest to India, low latency)"
  type        = string
  default     = "ap-south-1"
}

variable "instance_type" {
  description = "EC2 instance type — t3.micro is Free Tier eligible in ap-south-1 (1 vCPU, 1 GB RAM)"
  type        = string
  default     = "t3.micro"
}

variable "frontend_bucket_name" {
  description = "S3 bucket name for the React frontend — must be globally unique across all of AWS"
  type        = string
  default     = "sentinel-ui-951066974179"  # account ID suffix ensures global uniqueness
}

variable "key_pair_name" {
  description = "Name of an existing EC2 Key Pair for SSH access. Create one in AWS Console → EC2 → Key Pairs before running terraform apply."
  type        = string
  default     = ""
  # Leave empty to skip SSH key (you can still connect via AWS Systems Manager Session Manager)
}

variable "ollama_base_url" {
  description = "Ollama server URL — leave empty when running locally on EC2 (http://localhost:11434)"
  type        = string
  default     = ""
}

variable "review_min_evidence" {
  description = "Minimum negative feedback entries per doc type before the review agent calls the LLM. 1 = demo mode (any single thumbs-down produces a recommendation)."
  type        = number
  default     = 1
}
