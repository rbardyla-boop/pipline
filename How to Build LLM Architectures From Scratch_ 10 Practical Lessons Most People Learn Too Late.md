How to Build LLM Architectures From Scratch: 10 Practical Lessons Most People Learn Too Late  
Everyone wants to build AI products now.  
But most people skip the hard part:  
👉 Understanding how Large Language Model (LLM) architectures actually work.  
Today, it’s easier than ever to call an API from OpenAI, Anthropic, or Google.  
What’s difficult is building systems that are:

* Reliable  
* Scalable  
* Fast  
* Cost-efficient  
* Production-ready

That’s where architecture matters.  
Because an LLM product isn’t just “a chatbot.”  
Behind every serious AI product is an entire system handling:

* Context management  
* Retrieval  
* Tool usage  
* Memory  
* Prompt orchestration  
* Latency optimization  
* Agent workflows  
* Safety layers  
* Evaluation pipelines

The difference between a demo and a real AI product is usually architecture.  
Here are 10 practical lessons for building LLM architectures from scratch.

# 1\. Start With the Workflow, Not the Model

Most beginners obsess over:

* GPT-4  
* Claude  
* Gemini  
* Open-source benchmarks

But the model is only one layer.  
The real question is:  
👉 What workflow are you trying to automate?  
Examples:  
Customer Support AI  
Needs:

* Retrieval  
* Ticket memory  
* CRM integration  
* Human escalation

AI Research Assistant  
Needs:

* Web search  
* Citation systems  
* Long-context reasoning  
* Source ranking

AI Coding Agent  
Needs:

* Tool calling  
* Execution environment  
* File memory  
* Multi-step planning

Good architectures begin with system design—not model selection.

# 2\. Context Is Your Real Database

LLMs are extremely context-sensitive.  
The quality of outputs depends heavily on:

* What information enters the context window  
* How it’s formatted  
* What gets excluded

Most architecture problems are actually context problems.  
Bad systems:

* Dump everything into prompts  
* Waste tokens  
* Increase hallucinations

Good systems:

* Retrieve only relevant information  
* Compress intelligently  
* Rank context by importance

Think of context as working memory.  
Your job is deciding what deserves attention.

# 3\. Retrieval Is More Important Than Fine-Tuning

Most teams do NOT need fine-tuning first.  
They need better retrieval.  
This is why RAG (Retrieval-Augmented Generation) became foundational in modern AI systems.  
Instead of retraining the model, retrieve relevant knowledge dynamically.  
Core components include:

* Embedding models  
* Vector databases  
* Chunking pipelines  
* Re-ranking systems

A weak retrieval layer creates:

* Hallucinations  
* Wrong answers  
* Irrelevant outputs

Even powerful models fail with poor retrieval.

# 4\. Prompt Engineering Is Actually System Engineering

People treat prompts like magic spells.  
In reality:  
Prompt engineering is architecture design.  
A good prompt system includes:

* Role separation  
* Structured outputs  
* Tool instructions  
* Safety constraints  
* Memory formatting  
* Context prioritization

Production systems often use:

* Multi-prompt pipelines  
* Dynamic prompt injection  
* Hidden system prompts  
* Intermediate reasoning layers

The best AI products don’t use “one prompt.”  
They orchestrate many prompts together.

# 5\. Latency Matters More Than Intelligence

Users hate waiting.  
Even brilliant outputs feel broken if responses are slow.  
This is why architecture decisions must optimize:

* Token usage  
* Parallel calls  
* Caching  
* Retrieval speed  
* Streaming responses

Many successful AI products intentionally use:

* Smaller models first  
* Larger models only when necessary

Smart orchestration beats brute force.

# 6\. Agents Need Guardrails

Autonomous agents sound exciting.  
But uncontrolled agents become expensive and unreliable quickly.  
A production-ready agent architecture needs:

* Tool permission systems  
* Retry limits  
* Failure handling  
* Timeout logic  
* Action verification  
* Human checkpoints

Without guardrails:

* Infinite loops happen  
* Costs explode  
* Wrong actions compound

The more autonomy you add, the more control systems you need.

# 7\. Memory Is Harder Than Most People Expect

Memory isn’t just “saving chats.”  
Good memory systems require deciding:

* What should be remembered?  
* What should expire?  
* What should be summarized?  
* What matters long term?

Modern AI memory architectures often combine:

* Short-term context windows  
* Vector memory  
* Structured databases  
* Session summaries

Too much memory creates noise.  
Too little memory destroys personalization.  
Balance matters.

# 8\. Evaluation Pipelines Are Non-Negotiable

Most AI builders test manually.  
That doesn’t scale.  
You need evaluation systems that measure:

* Accuracy  
* Hallucination rates  
* Latency  
* Cost  
* Consistency  
* Tool success  
* User satisfaction

Strong AI teams build:

* Benchmark datasets  
* Regression testing  
* Automated evaluations  
* Human review loops

Without evaluation pipelines:  
You can’t improve reliably.  
You’re guessing.

# 9\. Cost Optimization Is Part of Architecture

Many AI apps fail because inference costs become unsustainable.  
Architecture decisions directly affect:

* Token consumption  
* API costs  
* Infrastructure usage

Simple optimizations matter:

* Context compression  
* Caching  
* Smaller routing models  
* Smart retrieval  
* Prompt shortening

Great AI systems aren’t just powerful.  
They’re economically sustainable.

# 10\. The Future Is Multi-Agent Systems

The next wave of AI products won’t rely on one giant prompt.  
They’ll use specialized agents working together.  
Examples:

* Research agent  
* Planning agent  
* Coding agent  
* Verification agent  
* Memory agent

Each handles a specific responsibility.  
This creates:

* Better reasoning  
* Modular systems  
* Easier debugging  
* Improved reliability

Instead of one overloaded model trying to do everything.

# Final Thoughts

Most people think building AI products is about choosing the smartest model.  
It’s not.  
The real advantage comes from:

* Architecture  
* Orchestration  
* Retrieval  
* Memory  
* Evaluation  
* Workflow design

LLMs are only the engine.  
The architecture is the vehicle.  
And the teams that understand this early will build the AI products that actually last.

# RMSNorm (Root Mean Square Layer Normalization)

Authors

*   
* ![Amit Shekhar][image1]  
* Name  
* Amit Shekhar  
* Published on  
* April 24, 2026

![RMSNorm (Root Mean Square Layer Normalization)][image2]  
In this blog, we will learn about RMSNorm, a faster and simpler alternative to [Layer Normalization](https://outcomeschool.com/blog/batch-normalization-vs-layer-normalization) that powers most modern Large Language Models like Llama, Mistral, Gemma, Qwen, PaLM, and DeepSeek.  
Our goal is to decode RMSNorm so clearly that by the end, we will be able to explain how it works to anyone.  
We will cover the following:

* Why normalization is needed in deep networks  
* A quick recap of Layer Normalization (LayerNorm)  
* What RMSNorm is and how it works  
* The math behind RMSNorm with a concrete numeric example  
* LayerNorm vs RMSNorm \- the key differences  
* Why modern LLMs prefer RMSNorm  
* A code example  
* Where RMSNorm fits in a Transformer  
* Quick Summary

I am Amit Shekhar, Founder @ [Outcome School](https://outcomeschool.com/), I have taught and mentored many developers, and their efforts landed them high-paying tech jobs, helped many tech companies in solving their unique problems, and created many open-source libraries being used by top companies. I am passionate about sharing knowledge through open-source, blogs, and videos.  
I teach [AI and Machine Learning](https://outcomeschool.com/program/ai-and-machine-learning) at Outcome School.  
Let's get started.

## The Big Picture

Before we go into the details, let's understand the big picture.  
Neural networks like LLMs stack many layers on top of each other. As numbers flow through these layers, they can become very big or very small. This makes training slow and unstable.  
To fix this, we scale the numbers at each layer to keep them in a healthy range. This scaling step is called normalization.  
In simple words:  
RMSNorm \= A simpler and faster way to normalize numbers inside a neural network.  
Instead of centering and scaling the numbers (like LayerNorm does), RMSNorm just scales them using their root mean square value. Same stabilizing effect, less work.

## Why Do We Need Normalization?

Let's say we have a deep neural network with 100 layers. At each layer, numbers get multiplied by weights, added together, and passed through activation functions.  
Here is the problem. After many layers, these numbers can:

* Become very large \- during training, this causes the exploding gradient problem  
* Become very small \- during training, this causes the vanishing gradient problem

When this happens, the network becomes unstable. Training slows down. Sometimes it does not learn at all.  
So, here comes normalization to the rescue. Normalization keeps the numbers at each layer in a stable, healthy range \- not too big, not too small. This makes training faster and more stable.

## A Quick Recap of Layer Normalization

Before jumping into RMSNorm, we must quickly recall how Layer Normalization (LayerNorm) works, because RMSNorm is a simplification of it.  
LayerNorm takes a vector of numbers and does two things:  
Step 1: Re-center. Subtract the mean so the numbers are centered around zero.  
Step 2: Re-scale. Divide by the standard deviation so the numbers have a consistent spread.  
Then it applies two learned parameters \- gamma and beta \- to allow the network to adjust the output if needed.  
The formula is:  
LayerNorm(x) \= gamma \* (x \- mean) / sqrt(variance \+ eps) \+ beta

Here:

* mean is the average of the values in the vector  
* variance is how spread out the values are  
* eps is a tiny number to avoid division by zero  
* gamma and beta are learned parameters

LayerNorm works very well. It was used in the original Transformer paper. But there is one question researchers asked:  
Do we really need both steps, re-centering and re-scaling? Or is one of them enough?  
This question led to RMSNorm.

## What Is RMSNorm?

RMSNorm (Root Mean Square Normalization) is a simpler version of LayerNorm that keeps only the re-scaling step and drops the re-centering step.  
In simple words:  
RMSNorm \= LayerNorm with only the re-scaling step.  
It was introduced in 2019 by Biao Zhang and Rico Sennrich in their paper "Root Mean Square Layer Normalization".  
The key insight was this:  
Most of the benefit of LayerNorm comes from the re-scaling step, not from the re-centering step.  
So, if we skip the mean subtraction, we save computation without losing accuracy.  
Here is a mental model that sticks:  
LayerNorm controls both shift and scale. RMSNorm controls only scale \- and that turns out to be enough.  
Now, a natural question arises \- if we do not re-center the values, how does the network handle mean shifts? The answer is that Transformers have residual connections and learned projections all over the place. These can absorb mean shifts on their own. So the network does not need normalization to do that job for it. The scale is the part that really needs a dedicated fix, which is why RMSNorm is enough in practice.  
Let's see exactly how it works.

## The Math Behind RMSNorm

RMSNorm uses the Root Mean Square (RMS) of the input vector to scale the values.  
We do three things, in order:  
Step 1: Square each value in the vector.  
Step 2: Take the mean (average) of those squared values.  
Step 3: Take the square root of that mean.  
That is it. The result is the RMS value.  
Intuitively, the RMS value tells us the typical magnitude of the numbers in the vector. A vector like \[100, 200, 300\] has a large RMS. A vector like \[0.01, 0.02, 0.03\] has a tiny RMS. By dividing each value by the RMS, we strip away the overall size and keep only the relative shape. That is exactly what we want from normalization.  
The formula is:  
RMS(x) \= sqrt( (x1^2 \+ x2^2 \+ ... \+ xn^2) / n )

Where n is the number of values in the vector.  
Once we have the RMS, the RMSNorm formula is:  
RMSNorm(x) \= gamma \* x / RMS(x)

Here:

* x is the input vector  
* RMS(x) is the root mean square of the vector  
* gamma is a learned parameter (one per dimension)

Why do we need gamma at all? Because dividing by the RMS forces every vector to a fixed magnitude, which is too restrictive. gamma gives the network a knob to stretch or shrink each dimension back to whatever scale is actually useful for the task. So normalization stabilizes training, and gamma makes sure we do not lose expressiveness along the way.  
In practice, we add a tiny number eps inside the square root to avoid division by zero:  
RMSNorm(x) \= gamma \* x / sqrt( mean(x^2) \+ eps )

Notice there is no beta in RMSNorm. We do not need to shift the output because we never subtracted the mean in the first place.

## Let's Put This Into Perspective With Real Numbers

Learning by example is the best way to learn.  
Let's say we have an input vector with 4 values:  
x \= \[2, 4, 4, 8\]

Step 1: Square each value.  
\[2^2, 4^2, 4^2, 8^2\] \= \[4, 16, 16, 64\]

Step 2: Take the mean of the squares.  
mean \= (4 \+ 16 \+ 16 \+ 64\) / 4 \= 100 / 4 \= 25

Step 3: Take the square root.  
RMS(x) \= sqrt(25) \= 5

Step 4: Divide each input value by the RMS.  
x / RMS(x) \= \[2/5, 4/5, 4/5, 8/5\] \= \[0.4, 0.8, 0.8, 1.6\]

Step 5: Multiply by gamma. For the sake of understanding, let's assume gamma is \[1, 1, 1, 1\].  
RMSNorm(x) \= \[0.4, 0.8, 0.8, 1.6\]

The numbers are now scaled to a healthy range. That is all RMSNorm does.

## LayerNorm vs RMSNorm \- The Key Differences

Let me tabulate the differences between LayerNorm and RMSNorm for your better understanding.

| LayerNorm | RMSNorm |
| :---- | :---- |
| Re-centers (subtracts mean) and re-scales (divides by std) | Only re-scales (divides by RMS) |
| Has two learned parameters: gamma and beta | Has one learned parameter: gamma |
| Slower \- computes both mean and variance | Faster \- only computes the RMS |
| Used in the original Transformer, BERT, GPT-2 | Used in Llama, Mistral, Gemma, Qwen, PaLM, DeepSeek |

To see the difference visually, here are the two pipelines side by side:  
LayerNorm:

 x  \--\>  \[ subtract mean \]  \--\>  \[ divide by std \]  \--\>  \[ \* gamma \+ beta \]  \--\>  output

RMSNorm:

 x  \--\>  \[    skipped     \]  \--\>  \[ divide by RMS \]  \--\>  \[    \* gamma     \]  \--\>  output

             ^^^^^^^                                            ^^^^^^^

       re-centering step                                     no beta,

           removed                                        one parameter

Here, we can see that RMSNorm drops the mean subtraction step completely and also drops the beta parameter. Everything else follows the same idea as LayerNorm.

## Why Modern LLMs Prefer RMSNorm

Now, a natural question arises \- why do most modern LLMs use RMSNorm instead of LayerNorm?  
The answer comes down to three reasons.  
Reason 1: Speed. RMSNorm does less math than LayerNorm. It skips the mean subtraction and the variance calculation. On a small vector, this may not look like much. But LLMs have billions of parameters, trillions of tokens, and dozens to hundreds of normalization calls per forward pass (two per Transformer block, stacked across many blocks). A small saving per call adds up to a big saving overall. The original paper reported training time reductions of 7% to 64% depending on the model and task. Training becomes faster. Inference becomes faster.  
Reason 2: Broadly the same accuracy. The original RMSNorm paper showed that models trained with RMSNorm reach the same accuracy as models trained with LayerNorm \- sometimes slightly better, sometimes slightly worse, but broadly the same. We get the speed benefit without losing quality.  
Reason 3: Simpler implementation. RMSNorm has fewer moving parts than LayerNorm. It is easier to implement and easier to reason about. With one less parameter (beta) and one less statistic to compute (the mean), the kernel is cleaner and easier to fuse efficiently on GPUs. This simplicity matters when we are training at the scale of trillions of tokens across thousands of GPUs.  
This is why the modern LLM stack has almost completely switched to RMSNorm.  
To learn LLM Internals, LLM Fundamentals, and Deep Learning hands-on with real projects, check out the [AI and Machine Learning Program](https://outcomeschool.com/program/ai-and-machine-learning) by Outcome School.

## A Code Example

Let's see the code for RMSNorm as below:  
import torch

import torch.nn as nn

class RMSNorm(nn.Module):

   def \_\_init\_\_(self, dim, eps=1e-6):

       super().\_\_init\_\_()

       self.eps \= eps

       self.gamma \= nn.Parameter(torch.ones(dim))

   def forward(self, x):

       \# Square each value and take the mean along the last dimension

       mean\_square \= x.pow(2).mean(dim=-1, keepdim=True)

       \# Take the square root to get RMS (eps added for stability)

       rms \= torch.sqrt(mean\_square \+ self.eps)

       \# Scale the input: divide by RMS and multiply by gamma

       return self.gamma \* x / rms

Here, we can see that:

* We only have one learned parameter \- gamma. There is no beta.  
* We compute the mean of the squared values along the last dimension.  
* We take the square root of that mean to get the RMS.  
* We divide the input by the RMS and multiply by gamma.

That is the entire implementation. It is very simple.

## Where RMSNorm Fits in a Transformer

In a modern LLM like Llama, RMSNorm is applied at two places inside each Transformer block:

* Before the attention block  
* Before the [feed-forward block](https://outcomeschool.com/blog/feed-forward-networks-in-llms)

This style is called pre-norm, which means we normalize the input first, then pass it through the attention or feed-forward layer. Pre-norm helps training stability in very deep networks, which is why almost all modern LLMs use it.  
Here is how one Transformer block looks with pre-norm RMSNorm:  
             input x

                |

     \+----------+              \<- residual path

     |          v

     |      \[ RMSNorm \]

     |          |

     |          v

     |      \[ Attention \]

     |          |

     \+--------\> (+)

                |

     \+----------+              \<- residual path

     |          v

     |      \[ RMSNorm \]

     |          |

     |          v

     |       \[ FFN \]

     |          |

     \+--------\> (+)

                |

                v

             output

Here, we can see that each RMSNorm sits before the heavy layer (Attention or FFN), not after. The residual path skips around the whole block so the original input can flow through untouched.  
One additional RMSNorm is also applied at the very end of the model, right before the final output projection. This last normalization keeps the hidden state in a stable range before it gets projected into logits.  
We have a detailed blog on [Transformer Architecture](https://outcomeschool.com/blog/decoding-transformer-architecture) that explains where normalization fits in the overall flow.  
If we want to go deep into Transformer Architecture, Attention, and Feed-Forward Networks end to end, check out the [AI and Machine Learning Program](https://outcomeschool.com/program/ai-and-machine-learning) by Outcome School.

## Quick Summary

Let's recap what we have learned:

* Normalization keeps the numbers flowing through a deep network in a healthy range, which makes training faster and more stable.  
* LayerNorm does two things \- it re-centers the values (subtracts the mean) and re-scales them (divides by standard deviation).  
* RMSNorm keeps only the re-scaling step. It divides the input by its Root Mean Square value.  
* Root Mean Square is exactly what the name says \- the square root of the mean of the squares.  
* RMSNorm is faster than LayerNorm because it skips the mean subtraction and the variance calculation.  
* Accuracy is broadly the same. The original paper showed RMSNorm matches LayerNorm on quality \- sometimes slightly better, sometimes slightly worse. We get the speed benefit essentially for free.  
* Modern LLMs like Llama, Mistral, Gemma, Qwen, PaLM, and DeepSeek all use RMSNorm.  
* Only one learned parameter \- gamma. It has one value per dimension of the vector. There is no beta in RMSNorm.

We have learnt how RMSNorm works, why it is faster than LayerNorm, and why most modern LLMs have adopted it.

# LLM Evaluation

Authors

*   
* ![Amit Shekhar][image3]  
* Name  
* Amit Shekhar  
* Published on  
* May 23, 2026

![LLM Evaluation][image4]  
In this blog, we will learn about LLM Evaluation. We will understand what it is, why we need it, the main types of evaluation, the automatic metrics and benchmarks we can use, human evaluation, LLM as a Judge, task-specific and safety evaluation, the common challenges, and the best practices to follow.  
We will cover the following:

* What is LLM Evaluation?  
* Why do we need LLM Evaluation?  
* Types of LLM Evaluation  
* Automatic Metrics  
* Benchmarks  
* Human Evaluation  
* LLM as a Judge  
* Task-Specific Evaluation  
* Safety and Red-Teaming Evaluation  
* Challenges in LLM Evaluation  
* Best Practices  
* When to use which method

I am Amit Shekhar, Founder @ [Outcome School](https://outcomeschool.com/), I have taught and mentored many developers, and their efforts landed them high-paying tech jobs, helped many tech companies in solving their unique problems, and created many open-source libraries being used by top companies. I am passionate about sharing knowledge through open-source, blogs, and videos.  
I teach [AI and Machine Learning](https://outcomeschool.com/program/ai-and-machine-learning) at Outcome School.  
Let's get started.

## What is LLM Evaluation?

LLM Evaluation is the process of measuring how well a Large Language Model performs on the tasks we expect it to do.  
In simple words, we give the model some inputs, look at the outputs, and check if the outputs are correct, helpful, safe, and useful. This is how we decide whether a model is good enough for our use case.  
Let's say we have built a chatbot using an LLM. Now, the question is: how do we know if our chatbot is actually good? Is it giving correct answers? Is it polite? Is it safe? Is it better than the older version we had last week? To answer all these questions, we need LLM Evaluation.

## Why do we need LLM Evaluation?

LLMs are very powerful, but they are not perfect. They can make mistakes. They can give wrong information. They can sound very confident even when they are wrong. This is called hallucination, where the model makes up facts that are not true. They can also produce harmful or biased content.  
So, before we ship an LLM to our users, we must know how it behaves. And after we ship it, we must keep checking it to make sure it does not get worse over time.  
Here are the main reasons we need LLM Evaluation:

* To compare different models and pick the best one for our use case.  
* To compare different versions of the same model after fine-tuning or prompt changes.  
* To find weak spots where the model fails so that we can fix them.  
* To make sure the model is safe and does not produce harmful content.  
* To track quality over time, so that we know if the model is getting better or worse.  
* To build trust with our users, our team, and our stakeholders.

Without evaluation, we are just guessing. And guessing is not a good idea when real users depend on our product.

## Types of LLM Evaluation

There are four main types of LLM Evaluation. We will learn about each of them in detail.

* Automatic Metrics \- We use formulas to score the model output against a reference answer.  
* Benchmarks \- We test the model on standard datasets that everyone uses.  
* Human Evaluation \- We ask humans to read the outputs and rate them.  
* LLM as a Judge \- We use another LLM to score the outputs.

Each of these has its own strengths and weaknesses. In real projects, we usually combine more than one of them.  
Beyond these four core methods, there are two cross-cutting areas we will also cover later in this blog: Task-Specific Evaluation and Safety Evaluation. These are not separate methods. They reuse the four above.  
Now, let's discuss each one.

## Automatic Metrics

Automatic Metrics are simple formulas that compare the model output with a reference answer and give us a score.  
The best way to learn this is by taking an example. Suppose we ask the model to translate a sentence from English to French. We already have the correct French translation written by a human. The model gives its own French translation. Now, we want to know how close the model's translation is to the human translation. This is where automatic metrics come into the picture.  
Here are the common ones:  
BLEU  
BLEU is used mostly for translation tasks. It is a precision-based metric. It asks: what fraction of small word groups (called n-grams) in the model output also appear in the reference answer? A higher BLEU score means the model output is closer to the reference. For example, if the reference is "The cat sat on the mat" and the model says "The cat sat on the mat", BLEU is very high. If the model says "A feline rested on the rug", BLEU is low even though the meaning is the same.  
ROUGE  
ROUGE is used mostly for summarization tasks. It asks: what fraction of n-grams in the reference summary are covered by the model summary? Just like BLEU, a higher score is better.  
BERTScore  
BERTScore uses contextual embeddings to compare the meaning of the model output with the reference. So, even if the words are different, if the meaning is close, the score is high. Going back to our earlier example, "A feline rested on the rug" would score high against "The cat sat on the mat" because the meaning is almost the same. This makes BERTScore much better than BLEU for tasks where the wording can vary a lot.  
METEOR  
METEOR is another metric that improves on BLEU by handling synonyms, stemming, and word order. It sits between pure surface matching and full semantic matching.  
Perplexity  
Perplexity measures how well the model predicts the next token. A lower perplexity means the model assigns a higher probability to the actual next token in the test data. This metric is mostly used during model training to track if the model is learning.  
Exact Match  
Exact Match is the simplest one. The score is 1 if the model output is exactly the same as the reference answer, and 0 otherwise. This is useful for tasks like math problems or short factual questions.  
Note: In modern LLM evaluation, reference-based metrics like BLEU and ROUGE are mostly used in research papers and translation pipelines. For production LLM applications, we usually rely on LLM as a Judge or task-specific evaluation, which we will learn about soon.  
Advantage:

* Fast and cheap to run.  
* We can run them at scale on millions of examples.  
* The scores are repeatable. Same input gives same score every time.

Disadvantage:

* They only check surface similarity. They do not understand meaning.  
* A model can give a perfect answer in different words and still get a low score.  
* They do not work well for open-ended tasks like creative writing or chat.

This was all about Automatic Metrics. Now, let's learn about Benchmarks.

## Benchmarks

Benchmarks are standard datasets that the whole research community uses to test LLMs.  
When a new LLM is released, the team behind it usually publishes scores on popular benchmarks. This helps us compare it with other models in a fair way.  
Different benchmarks test different skills. Let's group them by category, so that we know what each one is for.  
General Knowledge

* MMLU \- Tests general knowledge across 57 subjects like history, law, math, and medicine, using multiple-choice questions.  
* MMLU-Pro \- A harder version of MMLU with 10 answer choices and mandatory chain-of-thought reasoning.

Common Sense Reasoning

* HellaSwag \- The model has to pick the most likely ending to a short story.

Coding

* HumanEval \- Tests coding ability with simple function-writing problems.  
* SWE-bench Verified \- Real GitHub issues from open-source projects. Tests whether a model can solve real-world software problems.  
* LiveCodeBench \- A coding benchmark that uses problems released after the model's training cutoff, so it is contamination-resistant.

Math

* GSM8K \- Math word problems at the grade-school level.  
* MATH \- Harder competition-style math problems.  
* AIME \- Math olympiad problems used for advanced reasoning.

Frontier Reasoning

* GPQA-Diamond \- PhD-level science questions used to separate strong reasoning models from average ones.  
* Humanity's Last Exam (HLE) \- Over 3,000 expert-level questions across many fields, used as a hard frontier challenge.

Instruction Following

* IFEval \- Tests instruction-following with verifiable constraints, like "answer in exactly 3 bullet points".

Tool Use

* BFCL (Berkeley Function-Calling Leaderboard) \- Tests how well a model can use tools and call functions, very relevant for agents.

Long Context

* RULER \- Tests the effective context window, which is more honest than the nominal context length the model claims.

Truthfulness

* TruthfulQA \- Tests if the model gives truthful answers instead of repeating common false beliefs.

Conversation Quality

* Chatbot Arena (LMArena) \- Real users chat with two anonymous models side by side and pick the better one. The models are then ranked using an Elo score, just like in chess.

Now that we have seen the categories, we must understand three important ideas that decide how useful a benchmark really is.

* Saturation \- Over time, top models start scoring near the ceiling on a benchmark. When every model scores very high, the benchmark stops separating good from great. So, the research community keeps building harder benchmarks to take their place.  
* Data contamination \- The model may have seen the test questions during training, which makes the scores look higher than they really are. Contamination-resistant benchmarks try to fix this by using problems released after the model's training cutoff.  
* Qualification bar \- Older or easier benchmarks are not useless. They become a basic check that any serious model must pass before we even look at the harder ones.

Advantage:

* Easy to compare different models, because everyone uses the same dataset.  
* Covers a wide range of skills.  
* Backed by the research community.

Disadvantage:

* A high score on a benchmark does not always mean the model works well on our specific use case.  
* A benchmark can be saturated, contaminated, or both, which makes the scores misleading.  
* Public benchmarks rarely match the exact task we care about in our product.

This is how Benchmarks work. Now, let's move to Human Evaluation.  
To go deeper into how we evaluate LLMs and Agents, from automatic metrics to the benchmarks the whole research community relies on, check out the [AI and Machine Learning Program](https://outcomeschool.com/program/ai-and-machine-learning) by Outcome School.

## Human Evaluation

Human Evaluation is when real people read the model outputs and rate them.  
This is still the gold standard. Humans can judge things that formulas cannot, like tone, helpfulness, creativity, and safety.  
Let's say we ask the model to write a short poem. There is no single correct answer here. A formula cannot tell us if the poem is good. But a human reader can.  
Here are the common ways to do human evaluation:

* Likert Scale Rating \- The human gives a score from 1 to 5 on quality, helpfulness, or safety.  
* Pairwise Comparison \- The human sees two outputs and picks the better one. This is used in tools like Chatbot Arena.  
* Error Annotation \- The human marks the exact mistakes in the output, so we know where the model failed.

Advantage:

* Humans can judge meaning, tone, and quality.  
* Works for open-ended tasks where there is no single correct answer.  
* Gives us deep insights into where the model fails.

Disadvantage:

* Very slow and expensive.  
* Different humans may give different scores for the same output.  
* Hard to scale to thousands or millions of examples.

This was all about Human Evaluation. Now, let's learn about LLM as a Judge.

## LLM as a Judge

LLM as a Judge means we use a strong LLM to score the outputs of another LLM.  
Human evaluation is great but very expensive. So, here comes the LLM as a Judge to the rescue. We give a powerful model, like a top-tier LLM, the input prompt and the output, and we ask it to rate the output.  
For the sake of understanding, let's see an example. Suppose we want to check if a chatbot's reply is helpful and polite. We can write a prompt like this:  
You are an expert evaluator. Read the user question and the assistant reply.

Rate the reply on a scale of 1 to 5 for helpfulness and politeness.

Give a short reason for your rating.

User question: {question}

Assistant reply: {reply}

The judge LLM reads the prompt and gives us a score and a reason. We can then use this score just like a human score.  
Advantage:

* Much cheaper and faster than human evaluation.  
* Can scale to millions of examples.  
* Works well for open-ended tasks where formulas fail.

Disadvantage:

* The judge LLM can have its own biases. The well-known ones are:  
  * Position bias \- The judge can favor the first option, or sometimes the second, when comparing two answers side by side.  
  * Verbosity bias \- The judge can favor longer answers, even when a shorter one is better.  
  * Self-preference bias \- The judge can favor outputs from its own model family.  
* The judge is not perfect. It can also make mistakes.  
* We must validate the judge by comparing its scores with human scores on a small sample.

If you want to learn more about this, I have a separate blog on [LLM as a Judge](https://outcomeschool.com/blog/llm-as-a-judge) that goes deeper into this topic.  
This is how LLM as a Judge works. Now, it's time to learn about Task-Specific Evaluation.

## Task-Specific Evaluation

Task-Specific Evaluation is a layer on top of the four types we just learned. It means we design our own evaluation based on the exact task our LLM is doing.  
Under the hood, task-specific evaluation usually uses automatic metrics or LLM as a Judge. But the questions we ask, the inputs we test on, and the things we score are all chosen based on our specific use case.  
General benchmarks tell us how a model does on average. But, in our real product, we have a specific task. The evaluation must match that task.  
Let's see a few common cases.  
RAG (Retrieval Augmented Generation)  
In RAG, the model uses a retrieved document to answer a question. So, we need to check two things: did the system retrieve the right document, and did the model use the document correctly to answer the question?  
The standard here is the RAGAS four-metric pattern:

* Context Precision \- Of the chunks we retrieved, how many are actually relevant?  
* Context Recall \- Of all the relevant chunks in our corpus, how many did we manage to retrieve?  
* Faithfulness (Groundedness) \- Is the final answer supported by the retrieved context, or did the model make something up?  
* Answer Relevance \- Does the answer actually address the user's question?

There are popular frameworks that implement these metrics, like RAGAS, DeepEval. We do not need to learn all of them, but we must know that they exist so that we know what to search for when we build a real RAG system.  
Agents  
In agent systems, the model uses tools and takes many steps. So, we need to check:

* Did the agent pick the right tool?  
* Did it pass the correct arguments?  
* Did it finish the task?  
* How many steps did it take?

Two popular agent benchmarks worth knowing:

* τ-bench (tau-bench) \- Evaluates agents in realistic customer-service environments.  
* SWE-bench Verified \- For coding agents specifically, based on real GitHub issues.

Other names we will see are GAIA for general-assistant tasks, WebArena for browser agents, and BFCL for function-calling accuracy.  
Code Generation  
For code generation, we run the generated code against test cases. If the tests pass, the code is correct. This is much better than just comparing the code text.  
Customer Support Chatbots  
For chatbots, we check things like: did the bot answer the question, was the answer polite, did it follow our brand guidelines, and did it escalate to a human when needed.  
This way we can use Task-Specific Evaluation to solve any problem in a very simple way.  
If we want to go deep into RAG, Vector Databases, Tool use in Agents, and Multi-Agent Systems hands-on with real projects, check out the [AI and Machine Learning Program](https://outcomeschool.com/program/ai-and-machine-learning) by Outcome School.

## Safety and Red-Teaming Evaluation

Safety Evaluation is its own category, where we test the model against adversarial and harmful inputs.  
So far, we have focused on whether the model gives correct and useful answers. But, there is one more important question: is the model safe?  
In safety evaluation, we red-team the model with adversarial prompts. We try jailbreaks, prompt injections, and harmful requests. We check if the model refuses correctly, if it leaks sensitive data, and if it shows bias on sensitive topics.  
Here are some well-known safety benchmarks:

* HarmBench \- Tests model behavior on harmful and adversarial requests.  
* AdvBench \- A standard set of adversarial prompts used to attack models.  
* TrustLLM \- A broad evaluation suite covering truthfulness, safety, fairness, robustness, privacy, and ethics.

In production, we also run continuous safety monitoring on real traffic, because new attack patterns appear all the time.

## Challenges in LLM Evaluation

LLM Evaluation is hard. Here are the main challenges:

* Open-ended outputs \- There is no single correct answer for many tasks, so formulas do not work well. For example, there are a thousand ways to write a good email reply, and no formula can score all of them correctly.  
* Data contamination \- The model may have seen the test data during training, which makes the scores misleading.  
* Cost \- Human evaluation is expensive, and running large evaluation sets through powerful LLMs is also expensive.  
* Bias in the judge \- When we use LLM as a Judge, the judge can have its own preferences that do not match real users.  
* Drift over time \- The model behavior can change after fine-tuning, prompt updates, or even just because the provider updated the model on the backend. So, we must keep evaluating in production, not just before launch.  
* Edge cases \- The model may work well on average, but fail badly on rare but important cases. We must check for these and add them to our evaluation set.

Now, the next big question is: how do we deal with all these challenges? The answer is, we follow some best practices.

## Best Practices

Here are the best practices that I personally believe in for LLM Evaluation:

* Build a custom evaluation set \- Do not rely only on public benchmarks. Build a small but high-quality dataset that matches our real use case.  
* Combine many methods \- Use automatic metrics for speed, LLM as a Judge for scale, and human evaluation for the final check.  
* Validate the judge \- When using LLM as a Judge, compare its scores with human scores on a small sample to make sure the judge is reliable.  
* Track over time \- Run evaluations every time we change the prompt, the model, or the system. Save the results so we can see trends.  
* Cover edge cases \- Add hard examples, adversarial examples, and safety examples to our evaluation set.  
* Keep humans in the loop \- Even with automated evaluation, review a small sample by hand every week to catch problems that the metrics miss.  
* Measure cost and latency too \- Quality is not the only thing that matters. We must also track how fast the model responds and how much each call costs. A perfect answer that takes 30 seconds is not useful in a real product.

This way we can use LLM Evaluation to solve the interesting problem of knowing if our LLM is actually good.

## When to use which method

Let me tabulate the differences between the four evaluation methods for your better understanding so that you can decide which one to use based on your use case.

| Method | Speed | Cost | Quality of Judgement | Best For |
| :---- | :---- | :---- | :---- | :---- |
| Automatic Metrics | Very Fast | Very Low | Low | Translation, summarization, exact-answer tasks |
| Benchmarks | Fast | Low | Medium | Comparing models at the research level |
| Human Evaluation | Very Slow | Very High | Very High | Final quality check, open-ended tasks |
| LLM as a Judge | Fast | Medium | High | Scaling evaluation for chat, RAG, and agents |

Task-Specific and Safety Evaluation are not in this table, because they sit on top of these four methods. They decide what to test, and then they use these methods to do it.  
In a real product, we usually combine all four. We use automatic metrics during training, benchmarks for model selection, LLM as a Judge for daily monitoring, and human evaluation for the final check before shipping.  
This way we can use LLM Evaluation to build LLM applications that are reliable, safe, and useful for our users.

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,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>