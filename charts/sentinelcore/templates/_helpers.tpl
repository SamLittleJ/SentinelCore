{{- define "sentinelcore.labels" -}}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: sentinelcore
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "sentinelcore.tag" -}}
{{- required "image.tag names the images to run" .Values.image.tag -}}
{{- end }}

{{- /* One of our images, by digest when one is given (`make up
FROM=registry`), by tag otherwise. Called with (list . "backend"). */ -}}
{{- define "sentinelcore.image" -}}
{{- $root := index . 0 -}}
{{- $name := index . 1 -}}
{{- $digest := index $root.Values.image.digests $name -}}
{{- if $digest -}}
{{ index $root.Values.image $name }}@{{ $digest }}
{{- else -}}
{{ index $root.Values.image $name }}:{{ include "sentinelcore.tag" $root }}
{{- end -}}
{{- end }}

{{/* The pod's security settings, the same for every SentinelCore pod. */}}
{{- define "sentinelcore.podSecurity" -}}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- /* The backend image's own user (backend/Dockerfile), stated here so
the kubelet enforces it, whatever the image says. */ -}}
{{- define "sentinelcore.backendUser" -}}
runAsUser: 10001
runAsGroup: 10001
{{- end }}

{{- define "sentinelcore.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end }}

{{/* The API's settings (backend.config), for its pods and its Jobs. */}}
{{- define "sentinelcore.backendEnv" -}}
{{- range $name, $value := .Values.backend.config }}
- name: {{ $name }}
  value: {{ $value | quote }}
{{- end }}
{{- end }}
