<template>
  <div class="welcome-page">
    <AppGlowBg variant="rich" :orbs="true">
      <!-- 顶部品牌条 -->
      <header class="brand-bar">
        <div class="brand">
          <img :src="logo" alt="logo" class="brand-logo" />
          <div class="brand-text">
            <div class="brand-name">AI 智能测试平台</div>
            <div class="brand-sub">AutoTest Platform</div>
          </div>
        </div>
        <div class="brand-meta" v-if="userStore.userInfo?.username">
          <span class="brand-greet">Hi，{{ userStore.userInfo.username }}</span>
        </div>
      </header>

      <!-- Hero 区：插画 + 欢迎语 -->
      <section class="hero">
        <div class="hero-illust">
          <img :src="illustWelcome" alt="welcome" />
          <span class="illust-tag">
            <i class="i-solar-sparkles-bold" />
            v2.4.0
          </span>
        </div>
        <div class="hero-content">
          <div class="hero-eyebrow">
            <i class="i-solar-cpu-bolt-bold" />
            一站式智能测试解决方案
          </div>
          <h1 class="hero-title">
            欢迎使用 <span class="hero-grad">MSAITest 智能测试平台</span>
          </h1>
          <p class="hero-desc">
            <b>AI 大模型 + RAG 知识库</b>双引擎驱动，让 <b>用例生成</b>、<b>自动化执行</b>、<b>测试报告</b>、<b>缺陷分析</b>
            全流程更智能、更高效。
          </p>
          <div class="hero-actions">
            <el-button type="primary" size="large" class="cta-primary" @click="handleEnter">
              <i class="i-solar-rocket-2-bold" />
              开始使用
              <i class="i-solar-arrow-right-bold cta-arrow" />
            </el-button>
          
          </div>
          <div class="hero-hint">
            <i class="i-solar-shield-check-bold" />
            了解平台核心能力后，点击「开始使用」即可进入工作台
          </div>
        </div>
      </section>

      <!-- 功能卡片网格 -->
      <section class="features">
        <div class="features-head">
          <h2 class="features-title">
            <i class="i-solar-square-academic-cap-2-bold" />
            平台核心能力
          </h2>
          <p class="features-sub">{{ featureCards.length }} 大核心模块覆盖测试全流程 </p>
        </div>

        <div class="feature-grid">
          <div
            v-for="(card, idx) in featureCards"
            :key="card.title"
            class="feature-card"
            :class="`fc-${idx % 4}`"
            :style="{ animationDelay: `${idx * 60}ms` }"
          >
            <div
              class="fc-illust-wrap"
              role="img"
              :aria-label="card.title"
              :style="{ backgroundImage: `url(${card.illust})` }"
            />
            <div class="fc-body">
              <div class="fc-title">{{ card.title }}</div>
              <div class="fc-desc">{{ card.desc }}</div>
            </div>
          </div>

          <!-- 占位卡片：更多能力即将上线 -->
          <div
            v-for="(card, idx) in upcomingCards"
            :key="`upcoming-${card.title}`"
            class="feature-card fc-upcoming"
            :style="{ animationDelay: `${(featureCards.length + idx) * 60}ms` }"
          >
            <div
              class="fc-illust-wrap fc-illust-upcoming"
              role="img"
              :aria-label="card.title"
              :style="{ backgroundImage: `url(${card.illust})` }"
            />
            <div class="fc-body">
              <div class="fc-title">
                {{ card.title }}
                <span class="fc-soon-badge">
                  <i class="i-solar-clock-circle-bold" />
                  敬请期待
                </span>
              </div>
              <div class="fc-desc">{{ card.desc }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 底部统计条 -->
      <section class="stats">
        <div class="stat-item">
          <div class="stat-num">AI</div>
          <div class="stat-label">大模型驱动</div>
        </div>
        <div class="stat-sep" />
        <div class="stat-item">
          <div class="stat-num">RAG</div>
          <div class="stat-label">知识库增强</div>
        </div>
        <div class="stat-sep" />
        <div class="stat-item">
          <div class="stat-num">UI/API</div>
          <div class="stat-label">多端自动化</div>
        </div>
        <div class="stat-sep" />
        <div class="stat-item">
          <div class="stat-num">∞</div>
          <div class="stat-label">持续集成</div>
        </div>
      </section>

      <!-- 团队协作模块 -->
      <section class="team-banner">
        <div class="tb-illust">
          <img :src="illustTeam" alt="team" />
        </div>
        <div class="tb-content">
          <div class="tb-eyebrow">
            <i class="i-solar-users-group-rounded-bold" />
            团队协作
          </div>
          <h3 class="tb-title">让团队效率倍增，让测试人人参与</h3>
          <p class="tb-desc">
            项目成员共享用例库与执行结果，AI 实时推荐任务分配，
            让产品、设计、研发、测试在同一个平台上高效协同。
          </p>
          <div class="tb-meta">
            <span class="tb-tag"><i class="i-solar-check-circle-bold" /> 角色与权限</span>
            <span class="tb-tag"><i class="i-solar-check-circle-bold" /> 成员邀请</span>
            <span class="tb-tag"><i class="i-solar-check-circle-bold" /> 实时通知</span>
          </div>
        </div>
      </section>

      <!-- 底部 CTA + 备案 -->
      <footer class="welcome-footer">
        <el-button type="primary" size="large" class="cta-primary" @click="handleEnter">
          <i class="i-solar-rocket-2-bold" />
          开始使用
          <i class="i-solar-arrow-right-bold cta-arrow" />
        </el-button>
        <div class="copy">© {{ year }} MSAITest Platform · 让测试更智能</div>
      </footer>
    </AppGlowBg>
  </div>
</template>

<script setup lang="ts">import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import logo from '@/assets/brand/logo.svg';
import illustWelcome from '@/assets/illustrations/ai-agent.svg';
import illustCaseGen from '@/assets/illustrations/ai-case-gen.svg';
import illustExec from '@/assets/illustrations/ai-chat.svg';
import illustReport from '@/assets/illustrations/report.svg';
import illustWorkflow from '@/assets/illustrations/feature-workflow.svg';
import illustApi from '@/assets/illustrations/test-api.svg';
import illustWeb from '@/assets/illustrations/test-web.svg';
import illustPerformance from '@/assets/illustrations/test-performance.svg';
import illustApp from '@/assets/illustrations/test-app.svg';
import illustBug from '@/assets/illustrations/bug-fix.svg';
import illustKnowledge from '@/assets/illustrations/ai-knowledge.svg';
import illustEnv from '@/assets/illustrations/running.svg';
import illustAi from '@/assets/illustrations/ai-thinking.svg';
import illustTeam from '@/assets/illustrations/team.svg';
defineOptions({ name: 'WelcomeView' });
const router = useRouter();
const userStore = useUserStore();
const year = new Date().getFullYear();
interface FeatureCard {
    title: string;
    desc: string;
    icon?: string;
    illust: string;
}
const featureCards: FeatureCard[] = [
    {
        title: 'RAG 项目知识库',
        desc: '私有文档向量化检索，为 AI 提供更精准的业务上下文',
        icon: 'i-solar-book-bookmark-bold',
        illust: illustKnowledge,
    },
    {
        title: 'AI智能用例生成',
        desc: 'AI 基于知识库自动生成结构化测试用例，覆盖边界与异常路径',
        icon: 'i-solar-cpu-bolt-bold',
        illust: illustCaseGen,
    },
    {
        title: 'AI驱动 App 测试',
        desc: 'AI 驱动的移动端自动化，覆盖 Android / 鸿蒙 / iOS 真机与模拟器',
        icon: 'i-solar-smartphone-2-bold',
        illust: illustApp,
    },
    {
        title: '功能用例自动执行',
        desc: 'AI 驱动功能用例，自动执行，无需编写自动化脚本',
        icon: 'i-solar-rocket-2-bold',
        illust: illustExec,
    },
    {
        title: '业务流智能编排',
        desc: 'AI 辅助编排测试业务流，参数与数据智能装配',
        icon: 'i-solar-route-bold',
        illust: illustWorkflow,
    },
    {
        title: '缺陷管理',
        desc: '一键提单、生命周期跟踪、AI 辅助定位根因',
        icon: 'i-solar-bug-bold',
        illust: illustBug,
    },
    {
        title: '测试环境管理',
        desc: 'AI 智能推荐环境配置，自动管理多套测试环境、数据库与全局变量',
        illust: illustEnv,
    },
    {
        title: '智能测试报告分析',
        desc: 'AI 自动汇总失败原因、聚类缺陷、推荐修复方向',
        icon: 'i-solar-chart-2-bold',
        illust: illustReport,
    }
];
const upcomingCards: FeatureCard[] = [
    {
        title: '更多功能开发中',
        desc: '平台持续演进，AI 能力不断升级，敬请期待更多惊喜',
        illust: illustAi,
    },
];
const handleEnter = () => {
    // 标记已看过欢迎页，下次登录直接进项目
    try {
        localStorage.setItem('autotest:welcome_seen', '1');
    }
    catch {
        /* 忽略 */
    }
    router.replace('/workspace/projects');
};
const handleSkip = () => {
    handleEnter();
};
onMounted(() => {
    // 防御：未登录访问此页时跳回登录
    if (!userStore.isLoggedIn) {
        router.replace('/login');
    }
});
</script>

<style lang="scss" scoped>
.welcome-page {
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
}

/* ==================== 顶部品牌条 ==================== */
.brand-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 48px;
  position: relative;
  z-index: 1;

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-logo {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  }

  .brand-text {
    display: flex;
    flex-direction: column;
  }

  .brand-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: 0.5px;
  }

  .brand-sub {
    font-size: 11px;
    color: var(--text-tertiary, var(--text-secondary));
    letter-spacing: 1px;
  }

  .brand-greet {
    font-size: 13px;
    color: var(--text-secondary);
    padding: 6px 14px;
    background: var(--bg-card);
    border-radius: 9999px;
    border: 1px solid var(--border-light);
  }
}

/* ==================== Hero ==================== */
.hero {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 48px;
  align-items: center;
  padding: 32px 64px 64px;

  width: 100%;
  position: relative;
  z-index: 1;
}

.hero-illust {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;

  img {
    width: 100%;
    max-width: 460px;
    height: auto;
    filter: drop-shadow(0 24px 48px rgba(99, 102, 241, 0.18));
    animation: float 6s ease-in-out infinite;
  }

  .illust-tag {
    position: absolute;
    top: 12%;
    right: 8%;
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: 9999px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    color: var(--brand-500);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.12);
    display: flex;
    align-items: center;
    gap: 6px;

    i {
      font-size: 14px;
    }
  }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-12px); }
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--brand-glow-soft);
  color: var(--brand-500);
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 16px;

  i {
    font-size: 14px;
  }
}

.hero-title {
  font-size: 44px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-primary);
  margin: 0 0 20px;
  letter-spacing: -0.5px;
}

.hero-grad {
  background: linear-gradient(135deg, var(--brand-500), #8b5cf6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-desc {
  font-size: 16px;
  line-height: 1.75;
  color: var(--text-secondary);
  margin: 0 0 32px;
  max-width: 540px;

  b {
    color: var(--text-primary);
    font-weight: 600;
  }
}

.hero-actions {
  display: flex;
  gap: 14px;
  margin-bottom: 14px;
}

.cta-primary {
  padding: 16px 32px !important;
  font-size: 15px !important;
  border-radius: 12px !important;
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.25) !important;

  .cta-arrow {
    margin-left: 4px;
    transition: transform 0.2s ease;
  }

  &:hover .cta-arrow {
    transform: translateX(4px);
  }
}

.cta-ghost {
  padding: 16px 28px !important;
  font-size: 15px !important;
  border-radius: 12px !important;
}

.hero-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-tertiary, var(--text-secondary));

  i {
    font-size: 14px;
    color: var(--brand-500);
  }
}

/* ==================== 功能卡片 ==================== */
.features {
  padding: 32px 64px 56px;
  width: 100%;
  position: relative;
  z-index: 1;
  max-width: 1580px;
  margin: 0 auto;
}

.features-head {
  text-align: center;
  margin-bottom: 32px;
}

.features-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
  display: inline-flex;
  align-items: center;
  gap: 10px;

  i {
    font-size: 24px;
    color: var(--brand-500);
  }
}

.features-sub {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  justify-content: center;
}

.feature-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  padding: 26px 22px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  cursor: default;
  opacity: 0;
  transform: translateY(12px);
  animation: cardIn 0.5s ease forwards;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, transparent 50%, var(--card-accent, var(--brand-glow-soft)) 100%);
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
  }

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 16px 32px rgba(99, 102, 241, 0.1);
    border-color: var(--card-accent-border, var(--brand-200));

    &::before {
      opacity: 1;
    }
  }
}

@keyframes cardIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 4 个色系轮换 */
.fc-0 { --card-accent: rgba(99, 102, 241, 0.08); --card-accent-border: #c7d2fe; --card-color: #6366f1; }
.fc-1 { --card-accent: rgba(16, 185, 129, 0.08); --card-accent-border: #a7f3d0; --card-color: #10b981; }
.fc-2 { --card-accent: rgba(245, 158, 11, 0.08); --card-accent-border: #fde68a; --card-color: #f59e0b; }
.fc-3 { --card-accent: rgba(236, 72, 153, 0.08); --card-accent-border: #fbcfe8; --card-color: #ec4899; }

.fc-illust-wrap {

  height: 180px;
  background-color: var(--card-accent);
  /* 100% 100% 强制拉伸填满容器，覆盖 SVG 的 preserveAspectRatio="xMidYMid meet" */
  background-size: 100% 100%;
  background-repeat: no-repeat;
  background-position: center;
  border-radius: 12px 12px 0 0;
  margin: -26px -22px 18px;
  overflow: hidden;
}

.fc-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  position: relative;
}

.fc-desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  position: relative;
}

/* ==================== 统计条 ==================== */
.stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  padding: 32px 48px;
  margin: 0 auto;
  max-width: 960px;
  position: relative;
  z-index: 1;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}

.stat-num {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--brand-500), #8b5cf6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: -0.5px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
}

.stat-sep {
  width: 1px;
  height: 32px;
  background: var(--border-light);
}

/* ==================== 团队协作模块 ==================== */
.team-banner {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 48px;
  align-items: center;
  max-width: 1480px;
  margin: 0 auto 32px;
  padding: 32px 40px;
  background: linear-gradient(135deg, var(--brand-glow-soft), rgba(139, 92, 246, 0.06));
  border: 1px solid var(--border-light);
  border-radius: 20px;
  position: relative;
  z-index: 1;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at right top, rgba(99, 102, 241, 0.12), transparent 60%);
    pointer-events: none;
  }
}

.tb-illust {
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;

  img {
    width: 100%;
    max-width: 200px;
    height: auto;
    filter: drop-shadow(0 12px 24px rgba(99, 102, 241, 0.18));
  }
}

.tb-content {
  position: relative;
}

.tb-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  color: var(--brand-500);
  margin-bottom: 12px;

  i {
    font-size: 14px;
  }
}

.tb-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 10px;
  line-height: 1.3;
}

.tb-desc {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
  margin: 0 0 16px;
}

.tb-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tb-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 9999px;
  font-size: 12px;
  color: var(--text-regular);

  i {
    font-size: 13px;
    color: var(--color-success-500, #16a34a);
  }
}

@media (max-width: 768px) {
  .team-banner {
    grid-template-columns: 1fr;
    gap: 24px;
    padding: 24px;
    text-align: center;

    .tb-illust img {
      max-width: 160px;
    }

    .tb-meta {
      justify-content: center;
    }
  }
}

/* ==================== 底部 ==================== */
.welcome-footer {
  text-align: center;
  padding: 24px 48px 48px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.copy {
  font-size: 12px;
  color: var(--text-tertiary, var(--text-secondary));
  letter-spacing: 0.5px;
}

/* ==================== 响应式 ==================== */
@media (max-width: 1024px) {
  .hero {
    grid-template-columns: 1fr;
    text-align: center;
    padding: 24px 32px 40px;

    .hero-illust img {
      max-width: 320px;
    }

    .hero-actions,
    .hero-hint {
      justify-content: center;
    }

    .hero-desc {
      margin-left: auto;
      margin-right: auto;
    }
  }

  .feature-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .features {
    padding: 24px 32px 40px;
  }
}

@media (max-width: 600px) {
  .brand-bar {
    padding: 16px 20px;
  }

  .hero-title {
    font-size: 32px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .stats {
    flex-wrap: wrap;
    gap: 16px;

    .stat-sep {
      display: none;
    }
  }

  .stat-item {
    min-width: 80px;
  }
}
</style>