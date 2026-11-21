# The GitOps cluster (`make gitops-up`, docs/07-gitops.md): kind creates it
# and Helm installs Argo CD into it. Everything else comes from Git, through
# the root application scripts/gitops.sh applies once the Secrets exist. No
# Secret is created here: the state would keep it in plain text.

terraform {
  required_version = "= 1.17.2"

  # The state stays beside the cluster's other files, in .kind/gitops/
  # (git-ignored): scripts/gitops.sh gives the path to `terraform init`.
  backend "local" {}

  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "= 0.13.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "= 3.3.0"
    }
  }
}

variable "kubeconfig_path" {
  description = "Where kind writes the cluster's kubeconfig (.kind/gitops/kubeconfig)."
  type        = string
}

variable "argocd_chart" {
  description = "Argo CD's chart, downloaded and checked by scripts/tools.sh."
  type        = string
}

resource "kind_cluster" "gitops" {
  name            = "sentinelcore-gitops"
  kubeconfig_path = var.kubeconfig_path
  wait_for_ready  = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"
      # The node image of kind/kind-config.yaml, pinned by digest.
      image = "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"

      # The console's nodePort, on 8081 so `make up`'s cluster keeps 8080.
      extra_port_mappings {
        container_port = 30080
        host_port      = 8081
        listen_address = "127.0.0.1"
        protocol       = "TCP"
      }
    }
  }
}

provider "helm" {
  kubernetes = {
    host                   = kind_cluster.gitops.endpoint
    client_certificate     = kind_cluster.gitops.client_certificate
    client_key             = kind_cluster.gitops.client_key
    cluster_ca_certificate = kind_cluster.gitops.cluster_ca_certificate
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  chart            = var.argocd_chart
  namespace        = "argocd"
  create_namespace = true
  wait             = true
  timeout          = 600
  values           = [file("${path.module}/argocd-values.yaml")]
}
