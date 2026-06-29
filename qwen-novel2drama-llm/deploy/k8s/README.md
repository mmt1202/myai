# Kubernetes Deployment Profile

This folder is reserved for the production Kubernetes profile.

Required resources:

- API workload
- worker workload
- service object
- ingress object
- config map
- external secret reference
- migration job
- horizontal autoscaling policy
- readiness and liveness checks

Runtime checks:

- `/health`
- `/v1/ready`
- `/v1/health/deep`

This profile is repository-level and environment-neutral. A real cluster overlay must fill image, namespace, ingress class, host name, certificate issuer and secret references.
