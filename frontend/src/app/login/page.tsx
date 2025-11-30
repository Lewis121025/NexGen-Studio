"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import * as api from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);
  
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const handleLogin = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    
    if (!email) {
      setError("请输入邮箱");
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await api.login(email);
      
      // 保存认证信息到Store
      setAuth(response.access_token, response.user);
      
      // 跳转到Studio
      router.push("/studio");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <div className="w-full max-w-md space-y-8 rounded-lg bg-gray-800 p-8 shadow-2xl">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-white">Lewis AI System</h1>
          <p className="mt-2 text-sm text-gray-400">内测登录</p>
        </div>
        
        <form onSubmit={(e) => { void handleLogin(e); }} className="mt-8 space-y-6">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300">
              邮箱地址
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="your@email.com"
              disabled={isLoading}
            />
          </div>
          
          {error && (
            <div className="rounded-md bg-red-900/30 border border-red-700 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}
          
          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-white font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? "登录中..." : "登录"}
          </button>
          
          <p className="text-center text-xs text-gray-400">
            首次登录将自动创建账户 · 内测版本无需密码
          </p>
        </form>
        
        <div className="mt-6 rounded-md bg-blue-900/20 border border-blue-700 px-4 py-3">
          <p className="text-xs text-blue-200">
            <strong>内测提示：</strong>
            <br />
            • 每个新用户赠送 $50 额度
            <br />
            • 请确保已在 .env 中配置真实 API Key
            <br />
            • 需要帮助？查看 BETA_USER_GUIDE.md
          </p>
        </div>
      </div>
    </div>
  );
}
