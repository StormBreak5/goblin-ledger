import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatsCardProps {
    title: string;
    value: string | number;
    description?: string;
    trend?: "up" | "down" | "neutral";
    trendValue?: string;
    icon?: React.ReactNode;
    variant?: "default" | "success" | "warning" | "danger";
}

export function StatsCard({
    title,
    value,
    description,
    trend,
    trendValue,
    icon,
    variant = "default",
}: StatsCardProps) {
    const getTrendIcon = () => {
        switch (trend) {
            case "up":
                return <TrendingUp className="h-4 w-4 text-emerald-500" />;
            case "down":
                return <TrendingDown className="h-4 w-4 text-red-500" />;
            case "neutral":
                return <Minus className="h-4 w-4 text-slate-500" />;
            default:
                return null;
        }
    };

    const getVariantStyles = () => {
        switch (variant) {
            case "success":
                return "border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-emerald-500/5";
            case "warning":
                return "border-amber-500/20 bg-gradient-to-br from-amber-500/10 to-amber-500/5";
            case "danger":
                return "border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-500/5";
            default:
                return "border-slate-700";
        }
    };

    return (
        <Card className={getVariantStyles()}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardDescription className="flex items-center gap-2">
                        {icon}
                        {title}
                    </CardDescription>
                    {trend && trendValue && (
                        <Badge variant={trend === "up" ? "default" : trend === "down" ? "destructive" : "secondary"} className="gap-1">
                            {getTrendIcon()}
                            {trendValue}
                        </Badge>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-1">
                    <p className="text-3xl font-bold">{value}</p>
                    {description && (
                        <p className="text-sm text-muted-foreground">{description}</p>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
