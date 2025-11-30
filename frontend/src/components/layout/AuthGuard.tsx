"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";

import { setAuthToken } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

/**
 * 认证守卫组件
 * 检查用户是否已登录，未登录则重定向到登录页
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, token } = useAuthStore();
  
  useEffect(() => {
    // 同步Token到API客户端
    if (token) {
      setAuthToken(token);
    }
    
    // 如果在登录页，已登录则跳转到studio
    if (pathname === "/login") {
      if (isAuthenticated) {
        router.push("/studio");
      }
      return;
    }
    
    // 如果不在登录页且未登录，跳转到登录页
    if (!isAuthenticated && pathname !== "/login") {
      router.push("/login");
    }
  }, [isAuthenticated, token, pathname, router]);
  
  // 如果在登录页或已认证，直接渲染子组件
  if (pathname === "/login" || isAuthenticated) {
    return <>{children}</>;
  }
  
  // 未认证且不在登录页，显示加载中
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0A0A0F]">
      <div className="text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
        <p className="mt-4 text-gray-400">加载中...</p>
      </div>
    </div>
  );
}
