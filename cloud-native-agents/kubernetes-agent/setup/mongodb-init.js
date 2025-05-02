// mongodb-init.js
db = db.getSiblingDB('k8s_agent_platform');

// Create conversations collection with TTL index
db.createCollection('conversations');
db.conversations.createIndex({ "created_at": 1 }, { expireAfterSeconds: 7 * 24 * 60 * 60 }); // 7 days TTL
db.conversations.createIndex({ "user_id": 1 });
db.conversations.createIndex({ "cluster_id": 1 });

// Create messages collection
db.createCollection('messages');
db.messages.createIndex({ "conversation_id": 1 });
db.messages.createIndex({ "timestamp": 1 });

// Create tool_executions collection
db.createCollection('tool_executions');
db.tool_executions.createIndex({ "message_id": 1 });
db.tool_executions.createIndex({ "cluster_id": 1 });
db.tool_executions.createIndex({ "timestamp": 1 });

// Create agent_feedback collection
db.createCollection('agent_feedback');
db.agent_feedback.createIndex({ "message_id": 1 });
db.agent_feedback.createIndex({ "user_id": 1 });

// Create cluster_access collection
db.createCollection('cluster_access');
db.cluster_access.createIndex({ "cluster_id": 1 });
db.cluster_access.createIndex({ "user_id": 1 });

// Print initialization complete
print('MongoDB initialization completed');