BUILTIN_AI_INTRO_COURSE = {
    "slug": "ai-intro",
    "title": "人工智能导论",
    "description": (
        "面向高校学生的人工智能入门课程包，覆盖搜索、知识表示、机器学习、"
        "深度学习、自然语言处理、计算机视觉、多智能体和 AI 伦理安全。"
    ),
    "subject": "人工智能",
    "source_type": "builtin",
    "visibility": "public",
    "status": "ready",
    "material": {
        "filename": "人工智能导论内置课程包.md",
        "content_type": "text/markdown",
        "storage_path": "builtin://courses/ai-intro/course-pack.md",
        "parse_status": "completed",
        "metadata_json": {
            "source": "builtin_seed",
            "version": "2026-07-01",
            "language": "zh-CN",
            "course_slug": "ai-intro",
        },
    },
    "knowledge_points": [
        {
            "key": "ai-overview",
            "title": "人工智能概述",
            "summary": "理解人工智能的目标、发展脉络、典型任务和学习本课程的整体地图。",
            "chapter": "第 1 章 人工智能概述",
            "difficulty": "easy",
            "prerequisites": [],
            "chunks": [
                {
                    "section_title": "人工智能的基本目标",
                    "page_number": 1,
                    "content": (
                        "人工智能研究如何让机器表现出感知、推理、学习、规划和行动等智能行为。"
                        "课程学习时应先把 AI 看成一组解决问题的方法，而不是单一模型或工具。"
                    ),
                },
                {
                    "section_title": "人工智能任务版图",
                    "page_number": 2,
                    "content": (
                        "常见 AI 任务包括搜索与规划、知识表示、机器学习、自然语言处理、"
                        "计算机视觉和智能体协作。后续章节会从符号方法逐步过渡到数据驱动方法。"
                    ),
                },
            ],
        },
        {
            "key": "state-space-search",
            "title": "搜索问题与状态空间",
            "summary": "掌握状态、动作、初始状态、目标状态和路径代价等搜索问题基本要素。",
            "chapter": "第 2 章 搜索与问题求解",
            "difficulty": "easy",
            "prerequisites": ["ai-overview"],
            "chunks": [
                {
                    "section_title": "状态空间建模",
                    "page_number": 3,
                    "content": (
                        "搜索问题通常由初始状态、动作集合、状态转移、目标测试和路径代价构成。"
                        "把现实问题转换为状态空间，是使用搜索算法前最重要的建模步骤。"
                    ),
                },
                {
                    "section_title": "盲目搜索的特点",
                    "page_number": 4,
                    "content": (
                        "广度优先搜索、深度优先搜索和一致代价搜索不依赖额外领域知识。"
                        "它们适合讲清搜索框架，但在大规模状态空间中容易遇到组合爆炸。"
                    ),
                },
            ],
        },
        {
            "key": "heuristic-search",
            "title": "启发式搜索",
            "summary": "理解启发函数如何引导搜索，并能解释贪心搜索与 A* 搜索的差异。",
            "chapter": "第 2 章 搜索与问题求解",
            "difficulty": "medium",
            "prerequisites": ["state-space-search"],
            "chunks": [
                {
                    "section_title": "启发函数",
                    "page_number": 5,
                    "content": (
                        "启发式搜索使用启发函数估计当前状态到目标状态的距离。"
                        "好的启发函数能减少无效扩展，让搜索更快逼近可能的最优解。"
                    ),
                },
                {
                    "section_title": "A* 搜索",
                    "page_number": 6,
                    "content": (
                        "A* 搜索综合已经付出的路径代价 g(n) 和预计剩余代价 h(n)。"
                        "当启发函数可采纳且一致时，A* 能在图搜索中保证最优性。"
                    ),
                },
            ],
        },
        {
            "key": "knowledge-representation",
            "title": "知识表示",
            "summary": "了解命题逻辑、谓词逻辑、语义网络和规则系统的表达能力与局限。",
            "chapter": "第 3 章 知识表示与推理",
            "difficulty": "medium",
            "prerequisites": ["ai-overview"],
            "chunks": [
                {
                    "section_title": "符号知识表达",
                    "page_number": 7,
                    "content": (
                        "知识表示关注如何把事实、概念、关系和规则编码成机器可处理的结构。"
                        "逻辑表达适合精确推理，但面对不确定、模糊和海量数据时会遇到困难。"
                    ),
                },
                {
                    "section_title": "规则与推理",
                    "page_number": 8,
                    "content": (
                        "产生式规则使用 IF-THEN 形式表达知识，可支持前向推理和后向推理。"
                        "规则系统解释性较强，但知识获取和规则维护成本较高。"
                    ),
                },
            ],
        },
        {
            "key": "machine-learning-basics",
            "title": "机器学习基础",
            "summary": "建立样本、特征、标签、训练、泛化、损失函数和评估指标的基本概念。",
            "chapter": "第 4 章 机器学习基础",
            "difficulty": "easy",
            "prerequisites": ["ai-overview"],
            "chunks": [
                {
                    "section_title": "从规则到数据",
                    "page_number": 9,
                    "content": (
                        "机器学习不直接手写全部规则，而是从数据中学习模型参数或结构。"
                        "训练数据、特征表示、目标函数和评估方式共同决定模型是否可用。"
                    ),
                },
                {
                    "section_title": "泛化能力",
                    "page_number": 10,
                    "content": (
                        "模型不仅要在训练集上表现好，更要能处理未见过的数据。"
                        "过拟合表示模型记住了训练样本细节，却没有学到稳定规律。"
                    ),
                },
            ],
        },
        {
            "key": "supervised-learning",
            "title": "监督学习",
            "summary": "理解分类、回归、训练集、验证集、测试集以及常见监督学习流程。",
            "chapter": "第 4 章 机器学习基础",
            "difficulty": "medium",
            "prerequisites": ["machine-learning-basics"],
            "chunks": [
                {
                    "section_title": "分类与回归",
                    "page_number": 11,
                    "content": (
                        "监督学习使用带标签样本训练模型。分类任务预测离散类别，"
                        "回归任务预测连续数值，二者都需要明确输入特征和目标输出。"
                    ),
                },
                {
                    "section_title": "数据划分",
                    "page_number": 12,
                    "content": (
                        "训练集用于拟合模型，验证集用于选择超参数，测试集用于估计最终泛化性能。"
                        "如果把测试集反复用于调参，评估结果会变得过于乐观。"
                    ),
                },
            ],
        },
        {
            "key": "neural-networks",
            "title": "神经网络",
            "summary": "理解神经元、层、激活函数、前向传播和网络参数的基本含义。",
            "chapter": "第 5 章 神经网络与深度学习",
            "difficulty": "medium",
            "prerequisites": ["machine-learning-basics", "supervised-learning"],
            "chunks": [
                {
                    "section_title": "神经元与层",
                    "page_number": 13,
                    "content": (
                        "人工神经元对输入做加权求和，再通过激活函数产生输出。"
                        "多层神经网络通过组合简单变换，学习复杂的非线性映射。"
                    ),
                },
                {
                    "section_title": "激活函数",
                    "page_number": 14,
                    "content": (
                        "激活函数为网络引入非线性，使多层结构不再等价于单个线性模型。"
                        "常见激活函数包括 Sigmoid、Tanh、ReLU 及其变体。"
                    ),
                },
            ],
        },
        {
            "key": "backpropagation",
            "title": "反向传播",
            "summary": "掌握损失函数、梯度、链式法则和参数更新之间的关系。",
            "chapter": "第 5 章 神经网络与深度学习",
            "difficulty": "hard",
            "prerequisites": ["neural-networks"],
            "chunks": [
                {
                    "section_title": "梯度与链式法则",
                    "page_number": 15,
                    "content": (
                        "反向传播使用链式法则从输出层向前计算每个参数对损失的影响。"
                        "它不是独立模型，而是高效训练神经网络的一种求导方法。"
                    ),
                },
                {
                    "section_title": "参数更新",
                    "page_number": 16,
                    "content": (
                        "得到梯度后，优化器会沿着降低损失的方向更新参数。"
                        "学习率过大可能震荡或发散，过小则训练缓慢，需要结合验证效果调整。"
                    ),
                },
            ],
        },
        {
            "key": "natural-language-processing",
            "title": "自然语言处理",
            "summary": "了解分词、词向量、语言模型、文本分类、问答和生成式模型的基本任务。",
            "chapter": "第 6 章 自然语言处理",
            "difficulty": "medium",
            "prerequisites": ["machine-learning-basics", "neural-networks"],
            "chunks": [
                {
                    "section_title": "文本表示",
                    "page_number": 17,
                    "content": (
                        "自然语言处理需要把文本转换为模型可计算的表示。"
                        "从词袋模型到词向量，再到上下文表示，文本表示能力不断增强。"
                    ),
                },
                {
                    "section_title": "语言模型",
                    "page_number": 18,
                    "content": (
                        "语言模型学习一个词序列出现的概率，可用于补全、生成、摘要和问答。"
                        "大语言模型在海量语料上预训练，再通过指令或偏好数据对齐。"
                    ),
                },
            ],
        },
        {
            "key": "computer-vision",
            "title": "计算机视觉",
            "summary": "了解图像分类、目标检测、图像分割和视觉特征学习的基本思路。",
            "chapter": "第 7 章 计算机视觉",
            "difficulty": "medium",
            "prerequisites": ["machine-learning-basics", "neural-networks"],
            "chunks": [
                {
                    "section_title": "视觉任务",
                    "page_number": 19,
                    "content": (
                        "计算机视觉让机器从图像或视频中识别对象、场景、位置和关系。"
                        "图像分类回答是什么，目标检测回答在哪里，分割进一步给出像素级区域。"
                    ),
                },
                {
                    "section_title": "卷积神经网络",
                    "page_number": 20,
                    "content": (
                        "卷积神经网络通过局部连接和权值共享提取图像特征。"
                        "卷积层、池化层和全连接层组合后，可从边缘纹理逐步学习到高级语义。"
                    ),
                },
            ],
        },
        {
            "key": "agents-and-multi-agent",
            "title": "智能体与多智能体",
            "summary": "理解智能体的感知、决策、行动闭环，以及多智能体协作和冲突。",
            "chapter": "第 8 章 智能体系统",
            "difficulty": "medium",
            "prerequisites": ["ai-overview", "heuristic-search"],
            "chunks": [
                {
                    "section_title": "智能体闭环",
                    "page_number": 21,
                    "content": (
                        "智能体通过感知环境、维护状态、选择行动并观察反馈来完成任务。"
                        "在学习系统中，画像、检索、诊断、生成和审核可以拆成多个协作智能体。"
                    ),
                },
                {
                    "section_title": "多智能体协作",
                    "page_number": 22,
                    "content": (
                        "多智能体系统关注多个智能体之间的协调、通信、分工和冲突处理。"
                        "合理分工可以提升可解释性，但也需要记录过程轨迹，避免黑箱化。"
                    ),
                },
            ],
        },
        {
            "key": "ai-ethics-safety",
            "title": "AI 伦理与安全",
            "summary": "理解偏见、隐私、可解释性、鲁棒性、幻觉和人类监督等安全议题。",
            "chapter": "第 9 章 AI 伦理与安全",
            "difficulty": "medium",
            "prerequisites": ["machine-learning-basics"],
            "chunks": [
                {
                    "section_title": "可信 AI",
                    "page_number": 23,
                    "content": (
                        "可信 AI 不只追求准确率，还关注公平性、隐私保护、可解释性和安全边界。"
                        "教育场景尤其要避免泄露学生资料、误导学习判断或生成无依据内容。"
                    ),
                },
                {
                    "section_title": "幻觉与引用",
                    "page_number": 24,
                    "content": (
                        "生成式模型可能编造看似合理但没有依据的内容。"
                        "学习系统应通过 RAG 引用、低依据提示和审核机制降低幻觉风险。"
                    ),
                },
            ],
        },
    ],
}
