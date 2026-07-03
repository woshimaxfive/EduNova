import { describe, expect, it } from "vitest";

import { AGENT_ENDPOINTS } from "./agents";
import { AUTH_ENDPOINTS, login } from "./auth";
import { apiClient } from "./client";
import { COURSE_ENDPOINTS } from "./courses";
import { DASHBOARD_ENDPOINTS } from "./dashboard";
import { DEMO_ENDPOINTS } from "./demo";
import { MATERIAL_ENDPOINTS } from "./materials";
import { PATH_ENDPOINTS } from "./paths";
import { PRACTICE_ENDPOINTS } from "./practice";
import { RAG_ENDPOINTS, searchRag } from "./rag";
import { PROFILE_ENDPOINTS } from "./profiles";
import { REPORT_ENDPOINTS } from "./reports";
import { RESOURCE_ENDPOINTS } from "./resources";
import { getModelSettings, saveModelSettings, SETTINGS_ENDPOINTS, testModelSettings } from "./settings";
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
    expect(COURSE_ENDPOINTS.fromMaterials).toBe("/courses/from-materials");
    expect(COURSE_ENDPOINTS.masteryMap(7)).toBe("/courses/7/mastery-map");
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
                  chat_model: "deepseek-chat",
                  message: "模型连接成功。"
                }
              : {
                  source: "user",
                  provider: "openai_compatible",
                  base_url: "https://api.deepseek.com/v1",
                  chat_model: "deepseek-chat",
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
        chat_model: "deepseek-chat",
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
            chat_model: "deepseek-chat",
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
});
