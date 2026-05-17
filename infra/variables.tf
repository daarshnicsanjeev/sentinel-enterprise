variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type — t2.micro qualifies for Free Tier"
  type        = string
  default     = "t2.micro"
}

variable "ollama_base_url" {
  description = "Ollama Cloud endpoint URL (e.g. https://your-ollama-cloud.com)"
  type        = string
  sensitive   = true
}

variable "ollama_model" {
  description = "Ollama model tag to use"
  type        = string
  default     = "gemma4:31b-cloud"
}

variable "sentinel_api_key" {
  description = "Optional API key for protecting /api/* endpoints"
  type        = string
  default     = ""
  sensitive   = true
}

variable "project_name" {
  description = "Resource name prefix"
  type        = string
  default     = "sentinel"
}
