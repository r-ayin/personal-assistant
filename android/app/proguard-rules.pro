# 默认 proguard。release 未启用混淆（isMinifyEnabled=false），仅占位。
-keep class com.personalassistant.data.model.** { *; }
-keepclassmembers class * { @kotlinx.serialization.Serializable <fields>; }
