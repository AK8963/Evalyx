# Phase 1 Implementation Plan
**Status:** Starting implementation  
**Target:** Production readiness with 4 key features

---

## 📋 Phase 1 Feature Breakdown

### Feature 1: Permission System (Granular ACL) ⭐ HIGHEST PRIORITY
**Why First:** Other features depend on this (audit logs need user context, environment tags need permissions)

**Scope:**
- [ ] Add Role model to database (Owner, Admin, Editor, Viewer, Reviewer)
- [ ] Add ProjectACL & OrgACL database models
- [ ] Add permission checking middleware
- [ ] Create ACL management endpoints (`/api/acls/*`)
- [ ] Add permission verification to existing endpoints
- [ ] Frontend UI for permission management
- [ ] Environment variables for default roles

**Implementation Time:** 3-4 days  
**Files to Create/Modify:**
- `database/models.py` - Add Role, ProjectACL, OrgACL models
- `backend/routes/acls.py` - New ACL management endpoints
- `backend/middleware.py` - Permission checking
- `frontend/pages/permissions.py` - New permission management page
- `backend/config.py` - Add permission configuration

**Database Schema:**
```python
# New models needed:
class Role(Base):
    name: str  # owner, admin, editor, viewer, reviewer
    permissions: JSONB  # {"create_project": true, "delete_project": false, ...}

class ProjectACL(Base):
    project_id: UUID
    user_id: UUID
    role: str
    created_at: datetime

class OrgACL(Base):
    org_id: UUID
    user_id: UUID
    role: str
    created_at: datetime
```

---

### Feature 2: Audit Logging ⭐ SECOND PRIORITY
**Why Second:** Depends on permission system to know WHO did what

**Scope:**
- [ ] Create AuditLog database model
- [ ] Add audit logging middleware
- [ ] Log all CRUD operations (Create, Read, Update, Delete)
- [ ] Create audit query endpoints
- [ ] Add audit viewer page in frontend
- [ ] Export audit logs as JSON/CSV

**Implementation Time:** 2-3 days  
**Files to Create/Modify:**
- `database/models.py` - Add AuditLog model
- `backend/middleware.py` - Add audit logging middleware
- `backend/routes/audit.py` - Audit query endpoints (exists, needs enhancement)
- `frontend/pages/audit.py` - New audit viewer page

**Database Schema:**
```python
class AuditLog(Base):
    user_id: UUID
    action: str  # create, update, delete, login
    resource_type: str  # project, trace, experiment, etc
    resource_id: UUID
    changes: JSONB  # {before: {...}, after: {...}}
    ip_address: str
    user_agent: str
    timestamp: datetime
```

---

### Feature 3: Environment Tags ⭐ THIRD PRIORITY
**Why Third:** Builds on permission system, used by deployment features

**Scope:**
- [ ] Add environment field to Project & Prompt models
- [ ] Add environment endpoints (`/api/environments`)
- [ ] Create environment filter on traces/experiments
- [ ] Add environment selector to prompt deployment
- [ ] Add environment management to settings page
- [ ] Support environment variables per environment

**Implementation Time:** 2 days  
**Files to Create/Modify:**
- `database/models.py` - Add environment field to Project, Prompt
- `backend/routes/environments.py` - Environment management endpoints (exists, needs enhancement)
- `backend/routes/prompts.py` - Add environment support
- `frontend/pages/environments.py` - New environment management page
- `frontend/pages/prompts.py` - Add environment selector

**Database Schema:**
```python
# Add to Project model:
environments: JSONB  # {"dev": {...}, "staging": {...}, "prod": {...}}

# Add to Prompt model:
environment: str  # dev, staging, prod

class Environment(Base):
    project_id: UUID
    name: str  # dev, staging, prod
    config: JSONB  # environment-specific settings
    created_at: datetime
```

---

### Feature 4: BTQL Query Engine ⭐ LOWEST PRIORITY (but important)
**Why Last:** Complex, but can be iterated; others don't depend on it

**Scope (MVP):**
- [ ] Create simple SQL query interface
- [ ] Support WHERE, ORDER BY, LIMIT clauses
- [ ] Support basic GROUP BY with aggregations (COUNT, SUM, AVG)
- [ ] Add BTQL editor endpoint
- [ ] Add BTQL query endpoint
- [ ] Add query history
- [ ] Frontend SQL editor with syntax highlighting

**Implementation Time:** 4-5 days  
**Files to Create/Modify:**
- `backend/search/btql_engine.py` - New BTQL parser and executor
- `backend/routes/btql.py` - BTQL query endpoints
- `frontend/pages/btql.py` - SQL editor UI
- `database/` - Add support for complex queries

**Example BTQL Queries Supported:**
```sql
SELECT model, COUNT(*) as calls, AVG(latency) as avg_latency
FROM traces
WHERE timestamp > NOW() - INTERVAL '1 day'
GROUP BY model
ORDER BY calls DESC
LIMIT 10

SELECT * FROM traces
WHERE status = 'error'
AND project_id = 'xyz'
ORDER BY timestamp DESC
LIMIT 100
```

---

## 🎯 Implementation Order Recommendation

### Week 1: Permission System + Audit Logging
**Day 1-2:** Permission System (database + backend)  
**Day 3-4:** Audit Logging (database + backend)  
**Day 5:** Frontend for both (permissions + audit pages)

### Week 2: Environment Tags + BTQL MVP
**Day 1-2:** Environment Tags (backend)  
**Day 3:** BTQL Parser (backend query engine)  
**Day 4:** BTQL Executor + endpoints  
**Day 5:** Frontend (env manager + BTQL editor)

---

## 📊 Current Implementation Coverage

After Phase 1:
- ✅ Permission System: 0% → 90%
- ✅ Audit Logging: 10% → 85%
- ✅ Environment Tags: 0% → 100%
- ✅ BTQL: 0% → 60% (MVP)

**Overall improvement: 39% → ~52%**

---

## ⚡ Quick Start - Which Feature First?

**Option A: Start with Permissions** (Recommended)
- Unblocks other features
- Better foundation for everything else
- Estimated: 3-4 days

**Option B: Start with Audit Logging**
- Simpler to implement
- Good quick win
- Estimated: 2-3 days

**Option C: Start with Environment Tags**
- Good for DevOps workflows
- Medium complexity
- Estimated: 2 days

**Option D: Start with BTQL**
- Complex but powerful
- Can be iterated incrementally
- Estimated: 4-5 days

---

## Next Steps

**Choose one of the above options, and I will:**
1. Set up database migrations
2. Create models
3. Implement API endpoints
4. Build frontend UI
5. Add comprehensive tests
6. Document everything

What would you like to implement first?
