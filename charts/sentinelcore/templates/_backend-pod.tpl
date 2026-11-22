{{- /* The API's pod: the same for the Deployment (`make up`) and the Rollout
of the GitOps cluster's canary. */ -}}
{{- define "sentinelcore.backendPod" -}}
metadata:
  labels:
    app.kubernetes.io/name: sentinelcore-backend
    {{- include "sentinelcore.labels" . | nindent 4 }}
  annotations:
    sentinelcore/image-id: {{ .Values.image.ids.backend | quote }}
spec:
  serviceAccountName: sentinelcore-backend
  automountServiceAccountToken: false
  securityContext:
    {{- include "sentinelcore.podSecurity" . | nindent 4 }}
    {{- include "sentinelcore.backendUser" . | nindent 4 }}
  containers:
    - name: backend
      image: "{{ include "sentinelcore.image" (list . "backend") }}"
      imagePullPolicy: {{ .Values.image.pullPolicy }}
      # One uvicorn worker: Kubernetes runs more pods instead.
      env:
        {{- include "sentinelcore.backendEnv" . | nindent 8 }}
        - name: K8S_POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        # On every span: which build, where, and which pod sent it.
        - name: OTEL_RESOURCE_ATTRIBUTES
          value: "service.version={{ .Values.image.tag }},deployment.environment.name=kind,k8s.pod.name=$(K8S_POD_NAME)"
      envFrom:
        - secretRef:
            name: {{ .Values.secrets.api }}
        {{- /* None in a preview, whose API takes no Falco alerts. */}}
        {{- if .Values.secrets.falco }}
        - secretRef:
            name: {{ .Values.secrets.falco }}
        {{- end }}
      ports:
        - name: http
          containerPort: 8000
      startupProbe:
        httpGet:
          path: /health
          port: http
        periodSeconds: 2
        failureThreshold: 30
      livenessProbe:
        httpGet:
          path: /health
          port: http
        periodSeconds: 10
        timeoutSeconds: 3
      # Not ready without the database, or on a role that bypasses
      # row-level security.
      readinessProbe:
        httpGet:
          path: /health/ready
          port: http
        periodSeconds: 5
        timeoutSeconds: 3
      resources:
        {{- toYaml .Values.backend.resources | nindent 8 }}
      securityContext:
        {{- include "sentinelcore.containerSecurity" . | nindent 8 }}
      volumeMounts:
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: tmp
      emptyDir: {}
{{- end }}
