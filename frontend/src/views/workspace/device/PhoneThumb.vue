<script setup lang="ts">
/**
 * 设备缩略图（设备卡片用）—— 内联 SVG 的极简真机外观：
 * 深色机身 + 柔和渐变壁纸 + Home 条。小尺寸下保持干净。
 * 传入 shot（设备截图 objectURL）时，屏幕区显示真实画面（圆角裁切），
 * 否则回落默认壁纸。纯 SVG，截图由父组件带 token 拉取后传入。
 *
 * tablet=true 走平板外形（无刘海/灵动岛的简洁宽边框，屏幕区 3:4），
 * iPad 这类宽屏设备的截图不再被裁成竖条。手机保持窄长外形。
 */
withDefaults(defineProps<{ width?: number; shot?: string | null; tablet?: boolean }>(), {
  width: 64,
  shot: null,
  tablet: false,
})
</script>

<template>
  <div class="phone-thumb" :style="{ width: `${width}px` }">
    <!-- 平板：宽机身 + 3:4 屏幕，无刘海 -->
    <svg
      v-if="tablet"
      viewBox="0 0 150 200"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="平板缩略图"
    >
      <defs>
        <linearGradient id="ptWallT" x1="0" y1="0" x2="0.6" y2="1">
          <stop offset="0" stop-color="#eef7f1" />
          <stop offset="0.55" stop-color="#f6fafd" />
          <stop offset="1" stop-color="#eaf2fb" />
        </linearGradient>
        <radialGradient id="ptGlowT" cx="0.3" cy="0.25" r="0.9">
          <stop offset="0" stop-color="#bfe6cd" stop-opacity="0.55" />
          <stop offset="1" stop-color="#bfe6cd" stop-opacity="0" />
        </radialGradient>
        <clipPath id="ptScreenT">
          <rect x="7" y="7" width="136" height="186" rx="7" />
        </clipPath>
      </defs>

      <!-- 机身（窄边框:边到屏 7 单位,现代 iPad 全面屏观感） -->
      <rect x="1" y="1" width="148" height="198" rx="14" fill="#161a20" />
      <rect x="1.5" y="1.5" width="147" height="197" rx="13.5" fill="none" stroke="#30363f" stroke-width="1" />

      <!-- 屏幕：3:4，有截图显示真实画面，否则默认壁纸 -->
      <g clip-path="url(#ptScreenT)">
        <template v-if="shot">
          <image
            :href="shot"
            x="7"
            y="7"
            width="136"
            height="186"
            preserveAspectRatio="xMidYMid slice"
          />
        </template>
        <template v-else>
          <rect x="7" y="7" width="136" height="186" fill="url(#ptWallT)" />
          <rect x="7" y="7" width="136" height="186" fill="url(#ptGlowT)" />
        </template>
      </g>
    </svg>

    <!-- 手机：窄长机身 + 灵动岛 -->
    <svg v-else viewBox="0 0 92 194" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="手机缩略图">
      <defs>
        <linearGradient id="ptWall" x1="0" y1="0" x2="0.6" y2="1">
          <stop offset="0" stop-color="#eef7f1" />
          <stop offset="0.55" stop-color="#f6fafd" />
          <stop offset="1" stop-color="#eaf2fb" />
        </linearGradient>
        <radialGradient id="ptGlow" cx="0.3" cy="0.25" r="0.9">
          <stop offset="0" stop-color="#bfe6cd" stop-opacity="0.55" />
          <stop offset="1" stop-color="#bfe6cd" stop-opacity="0" />
        </radialGradient>
        <clipPath id="ptScreen">
          <rect x="5.5" y="5.5" width="81" height="183" rx="15" />
        </clipPath>
      </defs>

      <!-- 机身 -->
      <rect x="1" y="1" width="90" height="192" rx="20" fill="#161a20" />
      <rect x="1.5" y="1.5" width="89" height="191" rx="19.5" fill="none" stroke="#30363f" stroke-width="1" />
      <!-- 侧键 -->
      <rect x="90.4" y="52" width="1.6" height="18" rx="0.8" fill="#3a414b" />
      <rect x="90.4" y="78" width="1.6" height="28" rx="0.8" fill="#3a414b" />

      <!-- 屏幕：有截图显示真实画面，否则默认壁纸 -->
      <g clip-path="url(#ptScreen)">
        <template v-if="shot">
          <image
            :href="shot"
            x="5.5"
            y="5.5"
            width="81"
            height="183"
            preserveAspectRatio="xMidYMid slice"
          />
        </template>
        <template v-else>
          <rect x="5.5" y="5.5" width="81" height="183" fill="url(#ptWall)" />
          <rect x="5.5" y="5.5" width="81" height="183" fill="url(#ptGlow)" />
        </template>
      </g>

      <!-- 灵动岛 -->
      <rect x="35" y="10" width="22" height="6" rx="3" fill="#10131a" />

      <!-- Home 指示条 -->
      <rect x="35" y="181" width="22" height="3" rx="1.5" fill="#0f172a" fill-opacity="0.18" />
    </svg>
  </div>
</template>

<style scoped lang="scss">
.phone-thumb {
  flex-shrink: 0;

  svg {
    width: 100%;
    height: auto;
    display: block;
    filter: drop-shadow(0 3px 8px rgba(0, 0, 0, 0.16));
  }
}
</style>
