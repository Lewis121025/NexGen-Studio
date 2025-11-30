"use client";

import { Sparkles, Home, FolderOpen, Menu, LogOut, DollarSign, Shield } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import * as api from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

export default function AppLayout({ children }: { children: React.ReactNode }) {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const pathname = usePathname();
    const router = useRouter();
    const { user, clearAuth } = useAuthStore();

    const navigation = [
        { name: "工作区", href: "/studio", icon: Sparkles },
        { name: "首页", href: "/", icon: Home },
        { name: "库", href: "/library", icon: FolderOpen },
        { name: "治理", href: "/governance", icon: Shield },
    ];
    
    const handleLogout = async (): Promise<void> => {
        try {
            await api.logout();
            clearAuth();
            router.push("/login");
        } catch (error) {
            console.error("登出失败:", error);
            // 即使API调用失败，也清除本地状态
            clearAuth();
            router.push("/login");
        }
    };
    
    // 如果在登录页或 studio 页面，不显示 AppLayout 的侧边栏
    // studio 页面有自己的完整布局 (StudioWorkspace)
    if (pathname === "/login" || pathname === "/studio" || pathname.startsWith("/studio/")) {
        return <>{children}</>;
    }

    return (
        <div className="min-h-screen flex bg-[#0A0A0F] text-foreground">
            {/* Sidebar */}
            <aside className="hidden md:flex w-64 border-r border-white/10 bg-[#0F0F14]/80 backdrop-blur-xl flex-col">
                <div className="p-4 border-b border-white/10">
                    <Link href="/studio" className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                            <Sparkles className="h-4 w-4 text-white" />
                        </div>
                        <span className="font-semibold text-lg">Lewis AI</span>
                    </Link>
                </div>
                <nav className="flex-1 p-4 space-y-1">
                    {navigation.map((item) => {
                        const isActive = pathname === item.href || pathname.startsWith(`${item.href  }/`);
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                                    isActive
                                        ? "bg-white/10 text-white"
                                        : "text-gray-400 hover:bg-white/5 hover:text-white"
                                }`}
                            >
                                <item.icon className="h-5 w-5" />
                                {item.name}
                            </Link>
                        );
                    })}
                </nav>
                
                {/* User info and logout */}
                <div className="p-4 border-t border-white/10 space-y-2">
                    {user && (
                        <>
                            <div className="px-3 py-2 rounded-lg bg-white/5">
                                <p className="text-xs text-gray-400 truncate">{user.email}</p>
                                <div className="flex items-center gap-1 mt-1 text-green-400">
                                    <DollarSign className="h-3 w-3" />
                                    <span className="text-sm font-medium">{user.credits.toFixed(2)}</span>
                                </div>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => { void handleLogout(); }}
                                className="w-full justify-start text-gray-400 hover:text-white hover:bg-white/5"
                            >
                                <LogOut className="h-4 w-4 mr-2" />
                                登出
                            </Button>
                        </>
                    )}
                </div>
            </aside>

            {/* Mobile sidebar toggle */}
            <div className="md:hidden fixed top-4 left-4 z-50">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setSidebarOpen(!sidebarOpen)}
                    className="bg-[#0F0F14]/80 backdrop-blur-xl"
                >
                    <Menu className="h-5 w-5" />
                </Button>
            </div>

            {/* Main content */}
            <main className="flex-1 overflow-y-auto">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    {children}
                </div>
            </main>
        </div>
    );
}
