# translations.py
# 多语言翻译字典：支持 English 和 简体中文

TRANSLATIONS = {
    "en": {
        # ====== App Level ======
        "app_title": "Habitat Studio",
        "app_subtitle": "Data That Speaks",
        "navigate": "🧭 Navigate",
        "footer": "© 2025 Habitat Studio. All rights reserved.",

        # ====== Navigation Items ======
        "about": "🏠 About Us",
        "demo": "📊 Interactive Demo",
        "chatbot": "🤖 Ask Our Assistant",
        "message": "📢 Message Board",
        "contact": "📩 Contact Us",
        "admin": "🔐 Admin Panel",

        # ====== About Page ======
        "about_title": "🌍 About Habitat Studio",
        "about_intro": "### We Transform Data into Insights",
        "about_services": "#### 🔹 Our Services",
        "service_1": "- **Data Visualization & Dashboards** (Power BI, Tableau, Streamlit)",
        "service_2": "- **Predictive Analytics & Machine Learning**",
        "service_3": "- **ETL & Data Pipeline Development**",
        "service_4": "- **Custom Analytics Solutions**",
        "service_5": "- **Data Strategy & Consulting**",
        "about_why": "#### 🔹 Why Choose Us?",
        "why_1": "- Client-focused approach",
        "why_2": "- Rapid prototyping and iteration",
        "why_3": "- Clear communication and storytelling with data",
        "why_4": "- Built for scalability and real-world impact",
        "about_scenarios": "#### 🌐 Application Scenarios",
        "quote": '> *"Data is not just numbers — it\'s the story of your business."*',

        # ====== Industry Scenarios (EN) ======
        "scenarios_finance": "- **Finance**  \n  Visualize real-time stock prices and currency trends for faster investment decisions. Monitor banking KPIs, detect anomalies, and build interactive credit risk scoring models.",
        "scenarios_healthcare": "- **Healthcare**  \n  Track patient vitals like temperature and blood pressure in real time. Support clinical monitoring and research with intuitive visualizations of disease patterns and treatment outcomes.",
        "scenarios_education": "- **Education**  \n  Analyze student performance to identify learning patterns and at-risk individuals. Create interactive teaching materials that help students explore and understand data.",
        "scenarios_retail": "- **Retail & E-commerce**  \n  Monitor sales metrics (revenue, volume, profit) in real time. Analyze customer behavior to enable personalized marketing and recommendation engines.",
        "scenarios_logistics": "- **Logistics**  \n  Build live dashboards to track delivery times, route efficiency, and inventory levels—enabling dynamic adjustments for improved operations.",
        "scenarios_research": "- **Research**  \n  Turn complex experimental data into interactive visual stories in fields like physics and biology. Share exploratory analysis and findings with collaborators and audiences.",
        "scenarios_marketing": "- **Marketing**  \n  Analyze market trends, customer journeys, and campaign performance. Measure ROI and optimize strategies with data-driven insights.",

        # ====== Demo Page ======
        "demo_title": "📊 Interactive Demo",
        "demo_intro": "Explore our interactive data visualization demo below.",
        "demo_chart": "Sales Over Time",
        "demo_sidebar_title": "Filter Data",

        # ====== Chatbot Page ======
        "chatbot_title": "🤖 Ask Our Assistant",
        "chatbot_description": "Type a message to chat with our AI assistant.",
        "chatbot_input": "Your message...",
        "chatbot_send": "Send",
        "chatbot_welcome": "Hi! How can I help you today?",

        # ====== Message Board ======
        "message_title": "📢 Message Board",
        "message_description": "Leave us a public message!",
        "message_name": "Your Name",
        "message_content": "Your Message",
        "message_submit": "Submit Message",
        "message_success": "✅ Message posted successfully!",
        "message_loading": "Loading messages...",

        # ====== Contact Page ======
        "contact_title": "📩 Contact Us",
        "contact_intro": "Have questions or want to collaborate? Reach out!",
        "contact_name": "Name",
        "contact_email": "Email",
        "contact_subject": "Subject",
        "contact_message": "Message",
        "contact_send": "Send Message",
        "contact_success": "✅ Your message has been sent!",
        "contact_error": "❌ Please fill in all fields.",
        # ====== Contact Page - Enhanced Version ======
"contact_intro_full": "We'd love to hear from you. Fill out the form below and we'll get back to you soon.",
"contact_name_placeholder": "Enter your full name",
"contact_email_placeholder": "name@example.com",
"contact_subject_placeholder": "How can we help?",
"contact_message_placeholder": "Type your message here...",
"contact_error_name": "Please enter your name.",
"contact_error_email": "Please enter a valid email address.",
"contact_error_message": "Message cannot be empty.",
"contact_success_title": "✅ Thank you! Your message has been sent successfully.",
"contact_success_info": "We'll get back to you within 24 hours.",
"contact_init_error": "Unable to initialize message system.",
"contact_db_init_fail": "❌ Failed to initialize database: {error}",
"contact_save_fail": "❌ Failed to save message: {error}",
"contact_conn_fail": "🔗 Database connection failed: {error}",

        # ====== Admin Page ======
        "admin_title": "🔐 Admin Panel",
        "admin_password_prompt": "Enter Admin Password",
        "admin_wrong_password": "❌ Wrong password",
        "admin_messages_title": "📬 All Messages",
        "admin_no_messages": "📭 No messages yet.",
        # ====== Demo Page - Tabs & Sections ======
# General
        "demo_title": "Multi-Industry Data Analytics Platform",
        "demo_intro": "Explore how data is collected and visualized across industries.",
        "demo_data_acquisition": "Data Acquisition",
        "demo_dashboard": "Dashboard",
        "demo_datahub_title": "Data Hub",
        "demo_datahub_select": "Select a dataset to export:",
        "demo_datahub_download": "📥 Download {domain} Data as CSV",
        "demo_datahub_integration": "✅ This data can be integrated into ERP, BI, or AI systems.",
        "demo_datahub_connect": "🔗 Connect via API or export to CSV/Excel.",
       
        # Industries
        "demo_finance": "Finance",
        "demo_healthcare": "Healthcare",
        "demo_education": "Education",
        "demo_retail": "Retail",
        "demo_logistics": "Logistics",
        "demo_research": "Research",
        "demo_marketing": "Marketing",
        "demo_data_hub": "Data Hub",

        "demo_days": "days",
"demo_patients": "patients",
"demo_students": "students",
"demo_deliveries": "deliveries",
"demo_experiments": "experiments",
"demo_campaigns": "campaigns",

"demo_finance_generated": "financial records generated",
"demo_healthcare_generated": "patient records generated",
"demo_education_generated": "student records generated",
"demo_retail_generated": "retail records generated",
"demo_logistics_generated": "delivery records generated",
"demo_research_generated": "experiment records generated",
"demo_marketing_saved": "Campaign data saved!",

        # Finance
        "demo_finance_title": "Financial Market Dashboard",
        "demo_finance_stock_price": "Current Stock Price",
        "demo_finance_avg_volume": "Avg Daily Volume",
        "demo_finance_risk_level": "Risk Level",
        "demo_finance_stock_trend": "Stock Price Trend with 10-day MA",
        "demo_finance_stock_vs_currency": "Stock vs Currency Rate (Bubble Size = Volume)",
        "demo_finance_anomaly": "Anomaly detection system active.",

        "demo_finance_acquire_title": "Simulate Stock Market Data",
        "demo_finance_acquire_desc": "Adjust parameters to generate financial time series.",
        "demo_finance_initial_price": "Initial Price",
        "demo_finance_volatility": "Volatility (σ)",
        "demo_finance_days": "Number of Days",
        "demo_finance_generate": "Generate Data",

        # Healthcare
        "demo_healthcare_title": "Patient Vital Signs Monitor",
        "demo_healthcare_alert": "⚠️ {count} high-risk patients detected!",
        "demo_healthcare_normal": "✅ All patients within normal range.",
        "demo_healthcare_bp_dist": "Systolic Blood Pressure Distribution",
        "demo_healthcare_hypertension": "Hypertension Threshold",
        "demo_healthcare_oxygen": "Oxygen Level Over Time",
        "demo_healthcare_vital_corr": "Correlation Between Vital Signs",
        "demo_healthcare_alerts": "Alert system triggered based on BP and O₂ levels.",

        "demo_healthcare_acquire_title": "Generate Patient Monitoring Data",
        "demo_healthcare_acquire_desc": "Set patient count and data duration.",
        "demo_healthcare_num_patients": "Number of Patients",
        "demo_healthcare_duration": "Duration (days)",
        "demo_healthcare_generate": "Generate Vital Signs",

        # Education
        "demo_education_title": "Student Performance Analytics",
        "demo_education_at_risk": "Students at Risk",
        "demo_education_study_vs_score": "Study Hours vs Test Score",
        "demo_education_avg_score": "Average Score by Course",
        "demo_education_at_risk_list": "List of At-Risk Students",
        "demo_education_intervention": "Suggest personalized learning paths for at-risk students.",

        "demo_education_acquire_title": "Generate Student Dataset",
        "demo_education_acquire_desc": "Customize class size and course distribution.",
        "demo_education_num_students": "Number of Students",
        "demo_education_courses": "Courses Offered",
        "demo_education_generate": "Generate Student Data",

        # Retail
        "demo_retail_title": "Retail Sales Analytics",
        "demo_retail_revenue_share": "Revenue Share by Product",
        "demo_retail_daily_revenue": "Daily Revenue",
        "demo_retail_behavior": "Customer Age vs Revenue (Size = Units Sold)",
        "demo_retail_recommend": "Recommendation: Target marketing to 25–40 age group.",

        "demo_retail_acquire_title": "Generate Sales Transactions",
        "demo_retail_acquire_desc": "Set time range and product mix.",
        "demo_retail_days": "Recent Days",
        "demo_retail_products": "Products",
        "demo_retail_generate": "Generate Sales Data",

        # Logistics
        "demo_logistics_title": "Delivery Performance Dashboard",
        "demo_logistics_on_time": "On-Time Delivery Rate",
        "demo_logistics_delivery_time": "Delivery Time by Route",
        "demo_logistics_time_vs_dist": "Delivery Time vs Distance",
        "demo_logistics_fuel_cost": "Fuel Cost Distribution",
        "demo_logistics_optimize": "Optimize routes to reduce fuel cost.",

        "demo_logistics_acquire_title": "Generate Delivery Records",
        "demo_logistics_acquire_desc": "Configure number of deliveries and routes.",
        "demo_logistics_num_deliveries": "Number of Deliveries",
        "demo_logistics_routes": "Delivery Routes",
        "demo_logistics_generate": "Generate Delivery Data",

        # Research
        "demo_research_title": "Scientific Experiment Analysis",
        "demo_research_response": "Response Y vs Variable X",
        "demo_research_theoretical": "Theoretical Curve",
        "demo_research_significance": "Statistical Significance",
        "demo_research_significant": "p < 0.05",
        "demo_research_not_significant": "p ≥ 0.05",
        "demo_research_mean_response": "Mean Response by Group",
        "demo_research_communicate": "Communicate findings to stakeholders.",

        "demo_research_acquire_title": "Design Experiment Data",
        "demo_research_acquire_desc": "Control sample size and noise level.",
        "demo_research_sample_size": "Sample Size",
        "demo_research_noise": "Measurement Noise",
        "demo_research_generate": "Generate Experiment Data",

        # Marketing
        "demo_marketing_title": "Campaign Performance",
        "demo_marketing_roi": "Max ROI",
        "demo_marketing_cpc": "Min CPC",
        "demo_marketing_conv_rate": "Max Conversion Rate",
        "demo_marketing_revenue_roi": "Revenue vs ROI by Campaign",
        "demo_marketing_attribution": "Use multi-touch attribution for better insights.",

        "demo_marketing_acquire_title": "Input Campaign Results",
        "demo_marketing_acquire_desc": "Manually enter or simulate campaign data.",
        "demo_marketing_edit_data": "Edit Campaign Metrics Below",
        "demo_marketing_save": "Save & Visualize",
        # Marketing Campaign Metrics
        "demo_marketing_spend": "Spend",
        "demo_marketing_clicks": "Clicks",
        "demo_marketing_conversions": "Conversions",
        "demo_marketing_revenue": "Revenue",

        # Campaign Names
        "demo_campaign_spring_sale": "Spring Sale",
        "demo_campaign_summer_promo": "Summer Promo",
        "demo_campaign_back_to_school": "Back-to-School",
        "demo_campaign_holiday_blitz": "Holiday Blitz",

"demo_datahub_title": "📂 Unified Data Export Center",
"demo_datahub_select": "Select Dataset to Export",
"demo_datahub_download": "📥 Download {domain} Data as CSV",
"demo_datahub_integration": "### 🔗 Integration Ready",
"demo_datahub_connect": """
These dashboards can connect to:
- Databases (PostgreSQL, MySQL)
- Cloud APIs (Google Analytics, Stripe, Shopify)
- Real-time streams (Kafka, WebSockets)
- BI tools (Power BI, Tableau)
""",
# ====== Chatbot Page ======
"chatbot_title": "🤖 Ask Our Assistant",
"chatbot_description": "Type a message to chat with our AI assistant.",
"chatbot_input": "Your message...",
"chatbot_send": "Send",
"chatbot_welcome": "Hi! How can I help you today?",
"chatbot_clear": "🧹 Clear Conversation",
"chatbot_error": "❌ Failed to connect to AI model: {error}",
"chatbot_check": "Please check your `DASHSCOPE_API_KEY` in `.env` or network connection.",
# ====== Chatbot Services (EN) ======
"chatbot_service_1": "Understanding our data analytics services",
"chatbot_service_2": "Dashboard & visualization recommendations",
"chatbot_service_3": "Technical questions (Streamlit, Plotly, ML, etc.)",
"chatbot_service_4": "Project scoping or next steps",
"chatbot_instruction": "Just type your message below — I'll reply in the same language you use.",
# ====== Message Board ======
"message_title": "📢 Message Board",
"message_description": "Leave us a public message!",
"message_name": "Your Name",
"message_content": "Your Message",
"message_submit": "Submit Message",
"message_success": "✅ Message posted successfully!",
"message_loading": "Loading messages...",

# ====== Message Board - Community Version ======
"message_community_title": "💬 Community Message Board",
"message_community_intro": "Share your thoughts anonymously, or reply to others.",
"message_nickname": "Your temporary nickname (leave blank for 'Anonymous')",
"message_create_topic": "📝 Create a New Topic",
"message_post_title": "Title",
"message_post_content": "Your message",
"message_publish": "Publish Post",
"message_active_topics": "📬 Active Topics",
"message_no_posts": "No posts yet. Be the first to start a conversation!",
"message_comment_placeholder": "Add a comment",
"message_comment_button": "Comment",
"message_reply_placeholder": "Your reply",
"message_reply_button": "Reply",
"message_comment_posted": "💬 Comment posted!",
"message_failed_comment": "❌ Failed to post comment: {error}",
"message_failed_post": "❌ Failed to publish post: {error}",
"message_failed_load": "📥 Failed to load data: {error}",
"message_prev": "⬅️ Previous",
"message_next": "Next ➡️",
"message_page_info": "Page <b>{current}</b> of <b>{total}</b>",
# ====== Client Portal ======
"client": "💻 Client Portal",
"client_title": "💻 Client Project Portal",
"client_intro": "Log in to access your isolated project environment.",
"client_login": "User Login",
"client_username": "Username",
"client_password": "Password",
"client_login_button": "Log In",
"client_error_username": "Please enter username.",
"client_error_password": "Please enter password.",
"client_error_invalid": "Invalid username or password.",
"client_error_no_project": "Project not found: {project}",
"client_welcome": "Welcome",
"client_your_project": "Your assigned project",
"client_run_app": "▶️ Run Project App",
"client_running": "Running project...",
"client_logout": "Logout",
    },
    "zh": {
        # ====== App Level ======
        "app_title": "栖息地工作室",
        "app_subtitle": "让数据说话",
        "navigate": "🧭 导航",
        "footer": "© 2025 栖息地工作室。版权所有。",

        # ====== Navigation Items ======
        "about": "🏠 关于我们",
        "demo": "📊 交互式演示",
        "chatbot": "🤖 询问助手",
        "message": "📢 留言板",
        "contact": "📩 联系我们",
        "admin": "🔐 管理面板",

        # ====== About Page ======
        "about_title": "🌍 关于栖息地工作室",
        "about_intro": "### 我们将数据转化为洞察",
        "about_services": "#### 🔹 我们的服务",
        "service_1": "- **数据可视化与仪表盘** (Power BI, Tableau, Streamlit)",
        "service_2": "- **预测分析与机器学习**",
        "service_3": "- **ETL 与数据管道开发**",
        "service_4": "- **定制化分析解决方案**",
        "service_5": "- **数据战略与咨询**",
        "about_why": "#### 🔹 为什么选择我们？",
        "why_1": "- 以客户为中心",
        "why_2": "- 快速原型迭代",
        "why_3": "- 用数据讲好故事",
        "why_4": "- 面向可扩展性和实际影响",
        "about_scenarios": "#### 🌐 应用场景",
        "quote": '> “数据不只是数字——它是你业务的故事。”',

        # ====== Industry Scenarios (ZH) ======
        # ✅ 使用相同 key，不同语言内容
        "scenarios_finance": "- **金融**  \n  可视化实时股价和汇率趋势，辅助投资决策。监控银行关键指标，检测异常，并构建交互式信用风险评分模型。",
        "scenarios_healthcare": "- **医疗**  \n  实时追踪患者体温、血压等生命体征。通过直观可视化支持临床监测和疾病模式研究。",
        "scenarios_education": "- **教育**  \n  分析学生成绩以识别学习模式和潜在风险学生。创建互动教学材料，帮助学生探索和理解数据。",
        "scenarios_retail": "- **零售与电商**  \n  实时监控销售额、销量、利润等指标。分析用户行为，实现个性化营销与推荐系统。",
        "scenarios_logistics": "- **物流**  \n  构建实时看板，追踪配送时效、路线效率和库存水平，动态优化运营。",
        "scenarios_research": "- **科研**  \n  将物理、生物等领域的复杂实验数据转化为交互式可视化故事，便于分享分析结果。",
        "scenarios_marketing": "- **市场营销**  \n  分析市场趋势、用户旅程和广告表现，衡量 ROI 并优化数据驱动的营销策略。",

        # ====== Demo Page ======
        "demo_title": "📊 交互式演示",
        "demo_intro": "请查看下方的交互式数据可视化演示。",
        "demo_chart": "随时间变化的销售额",
        "demo_sidebar_title": "筛选数据",

        # ====== Chatbot Page ======
        "chatbot_title": "🤖 询问助手",
        "chatbot_description": "输入消息与我们的 AI 助手对话。",
        "chatbot_input": "你的消息...",
        "chatbot_send": "发送",
        "chatbot_welcome": "你好！今天我能帮你什么？",

        # ====== Message Board ======
        "message_title": "📢 留言板",
        "message_description": "给我们留下一条公开留言吧！",
        "message_name": "你的名字",
        "message_content": "你的留言",
        "message_submit": "提交留言",
        "message_success": "✅ 留言发布成功！",
        "message_loading": "正在加载留言...",

        # ====== Contact Page ======
        "contact_title": "📩 联系我们",
        "contact_intro": "有问题或想合作？请联系我们！",
        "contact_name": "姓名",
        "contact_email": "邮箱",
        "contact_subject": "主题",
        "contact_message": "消息内容",
        "contact_send": "发送消息",
        "contact_success": "✅ 消息已发送！",
        "contact_error": "❌ 请填写所有字段。",
        # ====== 联系我们页面 ======
"contact_intro_full": "我们很乐意收到你的消息。填写下方表单，我们会尽快回复。",
"contact_name_placeholder": "请输入你的全名",
"contact_email_placeholder": "name@example.com",
"contact_subject_placeholder": "有什么可以帮你的？",
"contact_message_placeholder": "在此输入你的消息...",
"contact_error_name": "请输入你的姓名。",
"contact_error_email": "请输入有效的邮箱地址。",
"contact_error_message": "消息内容不能为空。",
"contact_success_title": "✅ 谢谢！你的消息已成功发送。",
"contact_success_info": "我们将在 24 小时内回复你。",
"contact_init_error": "无法初始化留言系统。",
"contact_db_init_fail": "❌ 初始化数据库失败：{error}",
"contact_save_fail": "❌ 保存消息失败：{error}",
"contact_conn_fail": "🔗 数据库连接失败：{error}",

        # ====== Admin Page ======
        "admin_title": "🔐 管理面板",
        "admin_password_prompt": "请输入管理员密码",
        "admin_wrong_password": "❌ 密码错误",
        "admin_messages_title": "📬 所有留言",
        "admin_no_messages": "📭 暂无留言。",
# Main Industry Tabs
        "demo_finance": "金融",
        "demo_healthcare": "医疗",
        "demo_education": "教育",
        "demo_retail": "零售",
        "demo_logistics": "物流",
        "demo_research": "科研",
        "demo_marketing": "营销",
        "demo_data_hub": "数据中枢",  # ← 必须用下划线

        "demo_intro": "探索各行业数据的采集方式与可视化分析。",
        "demo_data_acquisition": "数据采集",
        "demo_dashboard": "数据仪表板",
        "demo_datahub_title": "数据中枢",
        "demo_datahub_select": "请选择要导出的数据集：",
        "demo_datahub_download": "📥 下载 {domain} 数据为 CSV",
        "demo_datahub_integration": "✅ 此数据可集成至 ERP、BI 或 AI 系统。",
        "demo_datahub_connect": "🔗 支持通过 API 或导出为 CSV/Excel 连接。",

        # Industries
        "demo_finance": "金融",
        "demo_healthcare": "医疗",
        "demo_education": "教育",
        "demo_retail": "零售",
        "demo_logistics": "物流",
        "demo_research": "科研",
        "demo_marketing": "营销",
        "demo_data_hub": "数据中枢",
 "demo_days": "天",
"demo_patients": "名患者",
"demo_students": "名学生",
"demo_deliveries": "个配送单",
"demo_experiments": "项实验",
"demo_campaigns": "个广告活动",

"demo_finance_generated": "条金融数据已生成！",
"demo_healthcare_generated": "条患者监测数据已生成！",
"demo_education_generated": "条学生成绩数据已生成！",
"demo_retail_generated": "条销售数据已生成！",
"demo_logistics_generated": "条配送记录已生成！",
"demo_research_generated": "条实验数据已生成！",
"demo_marketing_saved": "广告数据已保存！",
        # Finance
        "demo_finance_title": "金融市场仪表板",
        "demo_finance_stock_price": "当前股价",
        "demo_finance_avg_volume": "日均成交量",
        "demo_finance_risk_level": "风险等级",
        "demo_finance_stock_trend": "股价趋势（含10日均线）",
        "demo_finance_stock_vs_currency": "股价与汇率关系（气泡大小代表交易量）",
        "demo_finance_anomaly": "异常检测系统已启用。",

        "demo_finance_acquire_title": "模拟股票市场数据",
        "demo_finance_acquire_desc": "调整参数生成金融时间序列。",
        "demo_finance_initial_price": "初始价格",
        "demo_finance_volatility": "波动率 (σ)",
        "demo_finance_days": "天数",
        "demo_finance_generate": "生成数据",

        # Healthcare
        "demo_healthcare_title": "患者生命体征监控",
        "demo_healthcare_alert": "⚠️ 检测到 {count} 名高风险患者！",
        "demo_healthcare_normal": "✅ 所有患者生命体征正常。",
        "demo_healthcare_bp_dist": "收缩压分布",
        "demo_healthcare_hypertension": "高血压阈值",
        "demo_healthcare_oxygen": "血氧水平随时间变化",
        "demo_healthcare_vital_corr": "生命体征相关性分析",
        "demo_healthcare_alerts": "基于血压和血氧水平触发警报系统。",

        "demo_healthcare_acquire_title": "生成患者监测数据",
        "demo_healthcare_acquire_desc": "设置患者数量和监测时长。",
        "demo_healthcare_num_patients": "患者数量",
        "demo_healthcare_duration": "监测天数",
        "demo_healthcare_generate": "生成生命体征数据",

        # Education
        "demo_education_title": "学生成绩分析",
        "demo_education_at_risk": "高风险学生人数",
        "demo_education_study_vs_score": "学习时长与考试成绩",
        "demo_education_avg_score": "各课程平均分",
        "demo_education_at_risk_list": "高风险学生名单",
        "demo_education_intervention": "建议为高风险学生制定个性化学习路径。",

        "demo_education_acquire_title": "生成学生成绩数据",
        "demo_education_acquire_desc": "自定义班级规模和课程分布。",
        "demo_education_num_students": "学生人数",
        "demo_education_courses": "开设课程",
        "demo_education_generate": "生成学生成绩数据",

        # Retail
        "demo_retail_title": "零售销售分析",
        "demo_retail_revenue_share": "各产品收入占比",
        "demo_retail_daily_revenue": "每日收入",
        "demo_retail_behavior": "客户年龄与收入（大小代表销量）",
        "demo_retail_recommend": "建议：针对 25–40 岁客户群精准营销。",

        "demo_retail_acquire_title": "生成销售交易数据",
        "demo_retail_acquire_desc": "设置时间范围和产品组合。",
        "demo_retail_days": "最近天数",
        "demo_retail_products": "产品列表",
        "demo_retail_generate": "生成销售数据",

        # Logistics
        "demo_logistics_title": "配送绩效仪表板",
        "demo_logistics_on_time": "准时送达率",
        "demo_logistics_delivery_time": "各路线配送时间",
        "demo_logistics_time_vs_dist": "配送时间 vs 距离",
        "demo_logistics_fuel_cost": "燃油成本分布",
        "demo_logistics_optimize": "优化路线以降低燃油成本。",

        "demo_logistics_acquire_title": "生成配送记录",
        "demo_logistics_acquire_desc": "配置配送数量和路线。",
        "demo_logistics_num_deliveries": "配送单数",
        "demo_logistics_routes": "配送路线",
        "demo_logistics_generate": "生成配送数据",

        # Research
        "demo_research_title": "科研实验分析",
        "demo_research_response": "响应值 Y 与变量 X",
        "demo_research_theoretical": "理论曲线",
        "demo_research_significance": "统计显著性",
        "demo_research_significant": "p < 0.05",
        "demo_research_not_significant": "p ≥ 0.05",
        "demo_research_mean_response": "各组平均响应值",
        "demo_research_communicate": "向利益相关者传达研究发现。",

        "demo_research_acquire_title": "设计实验数据",
        "demo_research_acquire_desc": "控制样本量和测量噪声。",
        "demo_research_sample_size": "样本量",
        "demo_research_noise": "测量噪声",
        "demo_research_generate": "生成实验数据",

        # Marketing
        "demo_marketing_title": "广告活动表现",
        "demo_marketing_roi": "最高 ROI",
        "demo_marketing_cpc": "最低 CPC",
        "demo_marketing_conv_rate": "最高转化率",
        "demo_marketing_revenue_roi": "各活动收入与 ROI",
        "demo_marketing_attribution": "使用多触点归因模型获得更准确洞察。",

        "demo_marketing_acquire_title": "输入广告活动结果",
        "demo_marketing_acquire_desc": "手动输入或模拟广告数据。",
        "demo_marketing_edit_data": "请编辑以下广告活动指标",
        "demo_marketing_save": "保存并可视化",
        # Marketing Campaign Metrics
        "demo_marketing_spend": "支出",
        "demo_marketing_clicks": "点击量",
        "demo_marketing_conversions": "转化量",
        "demo_marketing_revenue": "收入",

        # Campaign Names
        "demo_campaign_spring_sale": "春季促销",
        "demo_campaign_summer_promo": "夏季促销",
        "demo_campaign_back_to_school": "返校季",
        "demo_campaign_holiday_blitz": "节日大促",

"demo_datahub_title": "📂 统一数据导出中心",
"demo_datahub_select": "选择要导出的数据集",
"demo_datahub_download": "📥 下载 {domain} 数据为 CSV",
"demo_datahub_integration": "### 🔗 无缝集成",
"demo_datahub_connect": """
这些仪表盘可连接：
- 数据库（PostgreSQL, MySQL）
- 云端 API（Google Analytics, Stripe, Shopify）
- 实时流（Kafka, WebSockets）
- BI 工具（Power BI, Tableau）
""",
# ====== 聊天机器人页面 ======
"chatbot_title": "🤖 询问助手",
"chatbot_description": "输入消息与我们的 AI 助手对话。",
"chatbot_input": "你的消息...",
"chatbot_send": "发送",
"chatbot_welcome": "你好！今天我能帮你什么？",
"chatbot_clear": "🧹 清除对话",
"chatbot_error": "❌ 连接 AI 模型失败：{error}",
"chatbot_check": "请检查 `.env` 文件中的 `DASHSCOPE_API_KEY` 或网络连接。",
# ====== 聊天机器人服务 (ZH) ======
"chatbot_service_1": "了解我们的数据分析服务",
"chatbot_service_2": "仪表盘与可视化建议",
"chatbot_service_3": "技术问题解答（Streamlit、Plotly、机器学习等）",
"chatbot_service_4": "项目规划或下一步建议",
"chatbot_instruction": "在下方输入消息——我会用你使用的语言回复。",
# ====== 留言板 - 社区版 ======
"message_community_title": "💬 社区留言板",
"message_community_intro": "你可以匿名发表想法，或回复他人。",
"message_nickname": "你的临时昵称（留空则为“匿名”）",
"message_create_topic": "📝 创建新话题",
"message_post_title": "标题",
"message_post_content": "你的内容",
"message_publish": "发布帖子",
"message_active_topics": "📬 活跃话题",
"message_no_posts": "暂无帖子。快来发起第一场对话吧！",
"message_comment_placeholder": "添加评论",
"message_comment_button": "评论",
"message_reply_placeholder": "你的回复",
"message_reply_button": "回复",
"message_comment_posted": "💬 评论已发布！",
"message_failed_comment": "❌ 发布评论失败：{error}",
"message_failed_post": "❌ 发布帖子失败：{error}",
"message_failed_load": "📥 加载数据失败：{error}",
"message_prev": "⬅️ 上一页",
"message_next": "下一页 ➡️",
"message_page_info": "第 <b>{current}</b> 页，共 <b>{total}</b> 页",
# ====== 客户门户 ======
"client": "💻 客户门户",  
"client_title": "💻 客户项目门户",
"client_intro": "登录以访问你的独立项目环境。",
"client_login": "用户登录",
"client_username": "用户名",
"client_password": "密码",
"client_login_button": "登录",
"client_error_username": "请输入用户名。",
"client_error_password": "请输入密码。",
"client_error_invalid": "用户名或密码错误。",
"client_error_no_project": "项目未找到：{project}",
"client_welcome": "欢迎",
"client_your_project": "你分配到的项目",
"client_run_app": "▶️ 运行项目应用",
"client_running": "正在运行项目...",
"client_logout": "退出登录",
    }
}