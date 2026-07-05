import { describe, expect, it } from "vitest";

import { AGENT_ENDPOINTS, getAgentTrace } from "./agents";
import { AUTH_ENDPOINTS, login } from "./auth";
import { apiClient } from "./client";
import { COURSE_ENDPOINTS, getCourseLearningState, updateCourseWeaknessReviewItem } from "./courses";
import { DASHBOARD_ENDPOINTS } from "./dashboard";
import { DEMO_ENDPOINTS } from "./demo";
import { MATERIAL_ENDPOINTS } from "./materials";
import { PATH_ENDPOINTS } from "./paths";
import { PRACTICE_ENDPOINTS } from "./practice";
import { RAG_ENDPOINTS, searchRag } from "./rag";
import { getMyProfile, listProfileEvents, PROFILE_ENDPOINTS, updateProfileByChat } from "./profiles";
import { REPORT_ENDPOINTS } from "./reports";
import { RESOURCE_ENDPOINTS } from "./resources";
import {
  createModelConfig,
  deleteModelConfig,
  getModelSettings,
  listModelConfigs,
  saveModelSettings,
  setDefaultModelConfig,
  SETTINGS_ENDPOINTS,
  testModelConfig,
  testModelSettings,
  updateModelConfig
} from "./settings";
import { listTutorSessions, TUTOR_ENDPOINTS } from "./tutor";

describe("frontend API contracts", () => {
  it("uses the documented API v1 base path", () => {
    expect(apiClient.defaults.baseURL).toBe("/api/v1");
  });

  it("keeps route constants aligned with docs/API.md", () => {
    expect(AUTH_ENDPOINTS.login).toBe("/auth/login");
    expect(AUTH_ENDPOINTS.me).toBe("/auth/me");
    expect(DASHBOARD_ENDPOINTS.summary).toBe("/dashboard/summary");
    expect(PROFILE_ENDPOINTS.chat).toBe("/profiles/chat");
    expect(PROFILE_ENDPOINTS.me).toBe("/profiles/me");
    expect(PROFILE_ENDPOINTS.events).toBe("/profiles/events");
    expect(COURSE_ENDPOINTS.fromMaterials).toBe("/courses/from-materials");
    expect(COURSE_ENDPOINTS.masteryMap(7)).toBe("/courses/7/mastery-map");
    expect(COURSE_ENDPOINTS.learningState(7)).toBe("/courses/7/learning-state");
    expect(COURSE_ENDPOINTS.weaknessReviewAction(7, "701", "confirm")).toBe(
      "/courses/7/weakness-review-items/701/confirm"
    );
    expect(MATERIAL_ENDPOINTS.upload).toBe("/materials/upload");
    expect(MATERIAL_ENDPOINTS.progress(3)).toBe("/materials/3/progress");
    expect(RAG_ENDPOINTS.search).toBe("/rag/search");
    expect(RESOURCE_ENDPOINTS.generate).toBe("/resources/generate");
    expect(AGENT_ENDPOINTS.trace("trace_demo")).toBe("/agents/traces/trace_demo");
    expect(PATH_ENDPOINTS.updateTask(9)).toBe("/paths/tasks/9");
    expect(TUTOR_ENDPOINTS.message(4)).toBe("/tutor/sessions/4/messages");
    expect(PRACTICE_ENDPOINTS.answers(8)).toBe("/practice/sessions/8/answers");
    expect(REPORT_ENDPOINTS.latest).toBe("/reports/latest");
    expect(DEMO_ENDPOINTS.reset).toBe("/demo/reset");
    expect(SETTINGS_ENDPOINTS.testModel).toBe("/settings/model/test");
    expect(SETTINGS_ENDPOINTS.configs).toBe("/settings/model/configs");
    expect(SETTINGS_ENDPOINTS.config(7)).toBe("/settings/model/configs/7");
    expect(SETTINGS_ENDPOINTS.testConfig(7)).toBe("/settings/model/configs/7/test");
    expect(SETTINGS_ENDPOINTS.defaultConfig(7)).toBe("/settings/model/configs/7/default");
  });

  it("posts login requests through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method,
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });

      return {
        data: {
          data: {
            access_token: "jwt-token",
            token_type: "bearer",
            user: {
              id: 1,
              email: "demo@edunova.local",
              display_name: "演示学生",
              role: "student"
            }
          },
          trace_id: "trace_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const response = await login({
        email: "demo@edunova.local",
        password: "Demo123456"
      });

      expect(calls).toEqual([
        {
          url: AUTH_ENDPOINTS.login,
          method: "post",
          data: {
            email: "demo@edunova.local",
            password: "Demo123456"
          }
        }
      ]);
      expect(response.data.access_token).toBe("jwt-token");
      expect(response.data.user.display_name).toBe("演示学生");
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("posts RAG search requests through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method,
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });

      return {
        data: {
          data: {
            course_id: 7,
            query: "启发式搜索",
            top_k: 5,
            results: []
          },
          trace_id: "trace_rag_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const response = await searchRag({
        course_id: 7,
        query: "启发式搜索",
        top_k: 5
      });

      expect(calls).toEqual([
        {
          url: RAG_ENDPOINTS.search,
          method: "post",
          data: {
            course_id: 7,
            query: "启发式搜索",
            top_k: 5
          }
        }
      ]);
      expect(response.data.results).toEqual([]);
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("uses typed profile API requests through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method,
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });

      return {
        data: {
          data:
            config.url === PROFILE_ENDPOINTS.events
              ? []
              : config.url === PROFILE_ENDPOINTS.chat
                ? {
                    reply: "已更新你的学习画像。",
                    profile: {
                      id: "1",
                      version: 1,
                      has_profile: true,
                      profile_json: {
                        major_background: "计算机专业大二",
                        knowledge_foundation: "机器学习刚入门",
                        learning_goal: "期末前掌握神经网络",
                        cognitive_style: "",
                        learning_preference: "",
                        weak_points: [],
                        learning_pace: "",
                        motivation_interest: ""
                      },
                      confidence_score: 64,
                      updated_reason: "更新学习画像：学习目标",
                      updated_at: "2026-07-05T09:00:00Z",
                      next_question: "你更喜欢哪种学习方式？"
                    },
                    event: {
                      id: "1",
                      dimension: "profile_chat",
                      change_summary: "更新学习画像：学习目标",
                      evidence_json: { source_type: "profile_chat", summary: "学生画像对话" },
                      created_at: "2026-07-05T09:00:00Z"
                    }
                  }
                : {
                    id: null,
                    version: 0,
                    has_profile: false,
                    profile_json: {
                      major_background: "",
                      knowledge_foundation: "",
                      learning_goal: "",
                      cognitive_style: "",
                      learning_preference: "",
                      weak_points: [],
                      learning_pace: "",
                      motivation_interest: ""
                    },
                    confidence_score: 0,
                    updated_reason: null,
                    updated_at: null,
                    next_question: "这门课你最想先解决什么问题？"
                  },
          trace_id: "trace_profiles_contract"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const profile = await getMyProfile();
      const updated = await updateProfileByChat({ message: "我想期末前掌握神经网络" });
      const events = await listProfileEvents();

      expect(calls).toEqual([
        { url: PROFILE_ENDPOINTS.me, method: "get", data: undefined },
        { url: PROFILE_ENDPOINTS.chat, method: "post", data: { message: "我想期末前掌握神经网络" } },
        { url: PROFILE_ENDPOINTS.events, method: "get", data: undefined }
      ]);
      expect(profile.data.has_profile).toBe(false);
      expect(updated.data.profile.profile_json.learning_goal).toBe("期末前掌握神经网络");
      expect(events.data).toEqual([]);
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("lists course tutor sessions with course_id through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string; params?: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method,
        params: config.params
      });

      return {
        data: {
          data: [],
          trace_id: "trace_tutor_course_sessions"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const response = await listTutorSessions("course", 7);

      expect(calls).toEqual([
        {
          url: TUTOR_ENDPOINTS.sessions,
          method: "get",
          params: {
            scope: "course",
            course_id: 7
          }
        }
      ]);
      expect(response.data).toEqual([]);
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("gets course learning state through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method
      });

      return {
        data: {
          data: {
            course_id: "7",
            profile_overlay: {
              learning_goal: "期末前掌握搜索算法",
              knowledge_foundation: "机器学习刚入门",
              weak_points: ["启发式搜索"]
            },
            weakness_summary: {
              candidate_event_count: 1,
              pending_count: 1,
              confirmed_count: 0,
              reviewing_count: 0,
              completed_count: 0,
              dismissed_count: 0,
              latest_evidence_at: "2026-07-05T08:30:00Z"
            },
            weakness_review_queue: [
              {
                id: "701",
                title: "启发式搜索",
                status: "pending",
                source_type: "course_question",
                course_id: "7",
                knowledge_point_id: "401",
                next_review_at: null,
                created_at: "2026-07-05T08:30:00Z",
                updated_at: "2026-07-05T08:30:00Z"
              }
            ],
            path_summary: {
              status: "not_started",
              message: "学习路径尚未生成。"
            },
            mastery_summary: {
              status: "not_started",
              message: "掌握度尚未接入。"
            },
            evidence_summary: {
              candidate_event_count: 1,
              latest_trace_id: "trace_candidate",
              latest_source_title: "人工智能导论讲义.md",
              latest_section_title: "启发式搜索"
            }
          },
          trace_id: "trace_learning_state"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const response = await getCourseLearningState(7);

      expect(calls).toEqual([{ url: COURSE_ENDPOINTS.learningState(7), method: "get" }]);
      expect(response.data.weakness_summary.pending_count).toBe(1);
      expect(response.data.weakness_review_queue[0].title).toBe("启发式搜索");
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("updates course weakness review items through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method
      });

      return {
        data: {
          data: {
            id: "701",
            title: "启发式搜索",
            status: "confirmed",
            source_type: "course_question",
            course_id: "7",
            knowledge_point_id: "401",
            next_review_at: null,
            created_at: "2026-07-05T08:30:00Z",
            updated_at: "2026-07-05T08:40:00Z"
          },
          trace_id: "trace_weakness_action"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const response = await updateCourseWeaknessReviewItem(7, "701", "confirm");

      expect(calls).toEqual([
        {
          url: COURSE_ENDPOINTS.weaknessReviewAction(7, "701", "confirm"),
          method: "post"
        }
      ]);
      expect(response.data.status).toBe("confirmed");
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("reads typed agent traces through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method
      });

      return {
        data: {
          data: {
            trace_id: "trace_candidate",
            course_id: "7",
            status: "completed",
            steps: [
              {
                id: "10",
                agent_name: "retrieve",
                step_index: 1,
                status: "completed",
                input_summary: "检索课程知识点",
                output_summary: "命中 2 条引用",
                duration_ms: 25,
                metadata: {
                  citation_count: 2,
                  review_result: "pass"
                },
                created_at: "2026-07-05T10:00:01Z"
              }
            ]
          },
          trace_id: "trace_agent_contract"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const response = await getAgentTrace("trace_candidate");

      expect(calls).toEqual([{ url: AGENT_ENDPOINTS.trace("trace_candidate"), method: "get" }]);
      expect(response.data.steps[0].agent_name).toBe("retrieve");
      expect(response.data.steps[0].metadata.citation_count).toBe(2);
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("uses typed model settings API requests through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method,
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });

      return {
        data: {
          data:
            config.method === "post"
              ? {
                  ok: true,
                  source: "user",
                  chat_model: "deepseek-v4-pro",
                  message: "模型连接成功。"
                }
              : {
                  source: "user",
                  provider: "openai_compatible",
                  base_url: "https://api.deepseek.com/v1",
                  chat_model: "deepseek-v4-pro",
                  embedding_model: "bge-m3",
                  has_api_key: true,
                  api_key_masked: "sk-u...cret",
                  can_use_model: true
                },
          trace_id: "trace_settings_contract"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      const summary = await getModelSettings();
      const saved = await saveModelSettings({
        provider: "openai_compatible",
        base_url: "https://api.deepseek.com/v1",
        api_key: "sk-user-secret",
        chat_model: "deepseek-v4-pro",
        embedding_model: "bge-m3"
      });
      const tested = await testModelSettings();

      expect(calls).toEqual([
        {
          url: SETTINGS_ENDPOINTS.model,
          method: "get",
          data: undefined
        },
        {
          url: SETTINGS_ENDPOINTS.model,
          method: "put",
          data: {
            provider: "openai_compatible",
            base_url: "https://api.deepseek.com/v1",
            api_key: "sk-user-secret",
            chat_model: "deepseek-v4-pro",
            embedding_model: "bge-m3"
          }
        },
        {
          url: SETTINGS_ENDPOINTS.testModel,
          method: "post",
          data: undefined
        }
      ]);
      expect(summary.data.source).toBe("user");
      expect(saved.data.api_key_masked).toBe("sk-u...cret");
      expect(tested.data.ok).toBe(true);
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });

  it("uses typed multi-model config API requests through the shared API client", async () => {
    const previousAdapter = apiClient.defaults.adapter;
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      calls.push({
        url: config.url,
        method: config.method,
        data: typeof config.data === "string" ? JSON.parse(config.data) : config.data
      });

      return {
        data: {
          data:
            config.url === SETTINGS_ENDPOINTS.configs && config.method === "get"
              ? {
                  configs: [],
                  default_config_id: null,
                  system_summary: {
                    source: "none",
                    provider: "openai_compatible",
                    base_url: null,
                    chat_model: null,
                    embedding_model: null,
                    has_api_key: false,
                    api_key_masked: null,
                    can_use_model: false
                  }
                }
              : config.url?.endsWith("/test")
                ? {
                    ok: true,
                    source: "user",
                    chat_model: "lite",
                    message: "模型连接成功。",
                    config_id: 3
                  }
                : {
                    id: 3,
                    source: "user",
                    display_name: "星火 Lite",
                    preset_id: "spark",
                    provider: "openai_compatible",
                    base_url: "https://spark-api-open.xf-yun.com/v1",
                    chat_model: "lite",
                    embedding_model: null,
                    has_api_key: true,
                    api_key_masked: "sp-u...oken",
                    can_use_model: true,
                    is_default: true,
                    last_test_ok: null,
                    last_test_message: null,
                    last_tested_at: null
                  },
          trace_id: "trace_model_configs"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    try {
      await listModelConfigs();
      await createModelConfig({
        display_name: "星火 Lite",
        preset_id: "spark",
        provider: "openai_compatible",
        base_url: "https://spark-api-open.xf-yun.com/v1",
        api_key: "spark-user-token",
        chat_model: "lite",
        make_default: true
      });
      await updateModelConfig(3, { chat_model: "4.0Ultra", api_key: "" });
      await setDefaultModelConfig(3);
      await testModelConfig(3);
      await deleteModelConfig(3);

      expect(calls).toEqual([
        { url: SETTINGS_ENDPOINTS.configs, method: "get", data: undefined },
        {
          url: SETTINGS_ENDPOINTS.configs,
          method: "post",
          data: {
            display_name: "星火 Lite",
            preset_id: "spark",
            provider: "openai_compatible",
            base_url: "https://spark-api-open.xf-yun.com/v1",
            api_key: "spark-user-token",
            chat_model: "lite",
            make_default: true
          }
        },
        { url: SETTINGS_ENDPOINTS.config(3), method: "patch", data: { chat_model: "4.0Ultra", api_key: "" } },
        { url: SETTINGS_ENDPOINTS.defaultConfig(3), method: "post", data: undefined },
        { url: SETTINGS_ENDPOINTS.testConfig(3), method: "post", data: undefined },
        { url: SETTINGS_ENDPOINTS.config(3), method: "delete", data: undefined }
      ]);
    } finally {
      apiClient.defaults.adapter = previousAdapter;
    }
  });
});
