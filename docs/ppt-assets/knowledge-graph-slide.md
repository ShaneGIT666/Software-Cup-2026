# PPT 素材：知识关系网络页

## 范围

轻量关系网络，不引入 Neo4j 等重依赖。

## 节点

- device
- component
- fault
- chunk
- case
- document
- review

## 关系

- device -> component
- device -> fault
- fault -> chunk
- fault -> case
- chunk -> document
- case -> review

## 约束

默认 approved-only，pending_review、rejected、deprecated、replaced 不进入正式图谱。
