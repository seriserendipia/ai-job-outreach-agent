# `feat/terraform-deploy` —— 部署到 GCP 的工作记录

> 本 branch 的 README。记录这次部署的目的、计划、进度、踩坑、当前下一步。
> 目标:**一次性 deploy 成功 → 截图 / 拿到运行中的 URL 写进简历 → `terraform destroy` 全部清理**。

---

## 1. 目的

支撑下面这条简历目标 JD bullet:

> **"Experience deploying resources via Terraform or similar tools to automate the setup of agents, functions, or networking."**

我们已有的 `master` 分支里实现了 multi-agent 后端(LangGraph)+ Chrome 扩展。这条 JD bullet 要求"用 Terraform 部署 agents / functions / networking"。把同一个多 agent 后端**用 IaC 方式部到 Google Cloud Run**,正好用一次完整的 Terraform 流程覆盖 JD 提到的全部关键词。

成功标准(写进简历的两条预期 bullet):

```
• Deployed the LangGraph agent backend to Google Cloud Run via Terraform —
  Artifact Registry, Cloud Run v2 service, Secret Manager for OpenAI / Tavily
  credentials, and a runtime service account with least-privilege IAM bindings.
• Automated build + deploy through GitHub Actions using Workload Identity
  Federation for OIDC-based GCP authentication — no long-lived service
  account keys.
```

---

## 2. 整体计划

### 2.1 架构(部署后)

```
[GitHub Actions]
   │ OIDC token
   ▼
[Workload Identity Federation]  ←──── 短期凭证,无长期 SA key
   │ impersonate
   ▼
[Service Account: ajoa-deployer]
   │
   ├─→ gcloud builds submit ──→  [Cloud Build]
   │                                  │
   │                                  ├─→ docker build (Dockerfile)
   │                                  └─→ push to → [Artifact Registry]
   │
   └─→ terraform apply ──→  [Cloud Run service: ajoa-backend]
                                 │ runtime SA: ajoa-runtime
                                 │ env from   ↓
                                 │   [Secret Manager: OPENAI_API_KEY, TAVILY_API_KEY, ...]
                                 │
                                 │ ingress: public HTTPS
                                 ▼
                              [Chrome extension → fetch backend URL]
```

### 2.2 文件结构(目标)

```
deploy/
├── README.md                  ← 本文件
├── ARCHITECTURE.md            ← 云无关描述(为以后可能迁移留)
├── Dockerfile                 ← 容器化 FastAPI backend (云无关)
├── .dockerignore
└── gcp/
    ├── README.md              ← Cloud Shell / 本地操作的 step-by-step
    ├── terraform.tfvars.example
    ├── backend.tf             ← state 存 GCS
    ├── providers.tf
    ├── variables.tf
    ├── locals.tf
    ├── apis.tf                ← google_project_service: 一次性启用各 API
    ├── artifact_registry.tf
    ├── service_account.tf
    ├── secrets.tf
    ├── cloud_run.tf
    ├── wif.tf                 ← Workload Identity Federation for GitHub
    ├── outputs.tf
    └── cloudbuild.yaml        ← 本地 / GHA 都能用
.github/
└── workflows/
    └── deploy.yml             ← OIDC → build → push → terraform apply
```

### 2.3 工具链

| 在哪 | 装什么 | 为什么 |
|---|---|---|
| 这个 Docker 容器(我用) | `google-cloud-cli` ~700MB + `terraform` ~50MB | 我直接 `gcloud` / `terraform` 跑命令,deploy 完一行卸 |
| 你的笔记本 | 零安装 | 唯一动作是点一次 OAuth URL + 把回来的 code 贴回聊天框 |
| GCP 账号 | 不用新开 —— **现有账号即可**($300 trial 与我们无关,Cloud Run/AR/SM/CB 都有永久免费 tier) | 单独建一个 project `ai-job-outreach-agent`,deploy 完 `gcloud projects delete` |

### 2.4 成本

| 项 | 月成本(portfolio 用量) |
|---|---|
| Cloud Run / AR / Secret Manager / Cloud Build / IAM | $0(永久免费 tier 内) |
| OpenAI / Tavily | demo 期间 ~$0.50 总额,事后停用 |
| 容器额外占用磁盘 | ~750MB 临时,deploy 完释放 |

---

## 3. 执行步骤(checklist)

| # | 步骤 | 谁 | 状态 |
|---|---|---|---|
| 1 | 容器装 terraform + gcloud | claude | ✅ |
| 2 | `gcloud auth login --no-launch-browser`,拿 URL | claude | ✅ |
| 3 | 浏览器走 OAuth,贴 code 回 claude | user | ✅ |
| 4 | `gcloud auth application-default login`(给 terraform 用,同样流程) | claude+user | ✅ |
| 5 | 决定 project_id;`gcloud projects create` 建新 project 或选现有 | claude | ✅ project=`ajoa-fwsjvo` |
| 6 | 启用必要 API(Cloud Run / AR / SM / CB / IAM Credentials 等) | claude | ✅ |
| 7 | 写 `deploy/Dockerfile` + `.dockerignore` | claude | ✅ |
| 8 | 写 `deploy/gcp/*.tf` 全部 | claude | ✅ |
| 9 | `terraform init` + `terraform plan` —— 你过 plan | claude→user | ✅ |
| 10 | `terraform apply`(经你 OK 后)| claude | ✅ 30 resources |
| 11 | `gcloud builds submit` 推首个镜像 | claude | ✅ image `:bfc2142` |
| 12 | 把真 secret 值塞 Secret Manager(或你给我我塞)| user/claude | ⬜ **需 user 提供 OPENAI/TAVILY key** |
| 13 | 端到端验证:`curl Cloud Run URL/health` | claude | ✅ `/health` 200 |
| 14 | 写 `.github/workflows/deploy.yml` + WIF 配置 | claude | ✅ |
| 15 | 推一次小改动到 master 测自动 deploy | claude | ⬜ **需 user push 到 GitHub** |
| 16 | 截图/录 URL 给简历 | user | ⬜ URL=`https://ajoa-backend-evzkfuxfda-uc.a.run.app` |
| 17 | `terraform destroy` 清资源 + `gcloud projects delete` | claude+user | ⬜ |
| 18 | 容器卸 gcloud + terraform | claude | ⬜ |

**当前部署状态:** Cloud Run service `ajoa-backend` 已经活在 `https://ajoa-backend-evzkfuxfda-uc.a.run.app`,运行的是真镜像 `:bfc2142`,`/health` 返回 200。Secrets 是 PLACEHOLDER 值,所以 `/compose`(调 LLM/Tavily)还跑不了。

---

## 4. 踩坑记录

> 部署过程中碰到的非显然问题,以及解决办法。每条:**症状 → 原因 → 解决**。

| 时间 | 症状 | 原因 | 解决 |
|---|---|---|---|
| Step 10 第一次 apply | Cloud Run `Error: Secret projects/.../OPENAI_API_KEY/versions/latest was not found` | Cloud Run 引用 `secret:latest` 时若 secret 没有任何 version 会启动失败。chicken-and-egg: TF 先建 `google_secret_manager_secret`(容器),没建 `google_secret_manager_secret_version`(实际值)。 | 在 `secrets.tf` 增加 `google_secret_manager_secret_version` placeholder 资源 + `lifecycle { ignore_changes = [secret_data] }`,后续 `gcloud secrets versions add` 不会被 TF 拉回 placeholder。 |
| Step 11 第一次 build | `gcloud builds submit` 上传 239MB + `invalid image name "...:": could not parse reference` | 1) `.gcloudignore` 不存在,默认行为没排掉 `backend/.venv`。2) `cloudbuild.yaml` 用了 `${SHORT_SHA}`,这个变量只在 GitHub/Cloud Build trigger 触发时由 CB 注入,manual `gcloud builds submit` 时是空。 | 1) 写项目根 `.gcloudignore` 显式排掉 `**/.venv`、tests、frontend 等。2) `cloudbuild.yaml` 改用 `_TAG`(自定义 substitution 默认 `latest`),手动 submit 时 `--substitutions=_TAG=$(git rev-parse --short HEAD)` 传入。 |
| Step 8 设计 image var | 第一次 apply 时 AR 还没镜像,Cloud Run service 会拉不到镜像。 | 经典 chicken-and-egg: AR repo 由 TF 建,镜像由 Cloud Build 推,但 Cloud Run service 一上来就要可用 image。 | `cloud_run.tf` 把 `image = var.image`,`variables.tf` 给 `var.image` 默认值 `us-docker.pkg.dev/cloudrun/container/hello`(Google 公开 placeholder)。第一次 apply 用 placeholder,Cloud Run 起得来;推完镜像后 `terraform apply -var=image=...:<sha>` 切换。 |

---

## 5. 下一步(claude 立即要做的)

**Step 1:在这个容器里装 `terraform` 和 `google-cloud-cli`。**

具体命令(待执行):

```bash
# Cloud SDK 官方源(避免 apt 自带版本太旧)
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/cloud.google.gpg
echo "deb [signed-by=/etc/apt/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
  | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get update

# Terraform 官方源
curl -fsSL https://apt.releases.hashicorp.com/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(. /etc/os-release && echo $VERSION_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update

# 装
sudo apt-get install -y google-cloud-cli terraform
gcloud --version
terraform -version
```

装完后:**跑 `gcloud auth login --no-launch-browser`**,把它打印的 URL 贴给你 → 你笔记本浏览器走 OAuth → 把 verification code 贴回来 → 我把 code 喂给等待的 gcloud 进程 → 认证完成。

之后所有命令我直接跑,看到结果,出错自己 debug。

---

**文件位置:** `deploy/README.md` (绝对路径 `/workspace/ai-job-outreach-agent/deploy/README.md`)
