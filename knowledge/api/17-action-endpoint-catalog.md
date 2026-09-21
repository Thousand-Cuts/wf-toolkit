# 17 — Action endpoint catalog

Every named action endpoint Adobe publishes for the Workfront REST API: **426 endpoints across
69 objects**, extracted from Adobe's own OpenAPI document
(`AdobeDocs/workfront-apis`, vendored at `adobe-openapi/workflow.json`).

An "action" here is anything beyond the standard verbs. Every object already answers
`GET/POST/PUT/DELETE` plus `/count`, `/search`, `/report` and `/metadata`; those are
`05-http-methods-and-actions.md`. This file is the rest: `bulkMove`, `advancedCopy`,
`attachTemplate`, `calculateTimeline`, `acknowledgeMany` and 400 or so others, most of which have
no Experience League page at all.

## Read this before you use it

**The spec is v19.0. The toolkit pins v22.0.** Adobe publishes one OpenAPI document and it trails
the current version. The endpoint surface is the most stable part of the API, so treat this as a
reliable map of *what exists*, and confirm against the tenant before you depend on any single
endpoint:

```bash
bash skills/_shared/scripts/wf-env-curl.sh /attask/api/v22.0/<obj>/metadata | python3 -m json.tool | grep -i '<action>'
```

`14-api-version-drift.md` covers what moved between v20 and v22.

**Parameters, not fields.** Adobe's schemas are external `$ref`s resolved at build time from a live
tenant, so the vendored document carries no field definitions. What it does carry, and what is
listed here, is each action's **query parameters**, which is the part that is otherwise
undiscoverable without trial and error. `*` marks required; `[]` marks an array parameter.

**`[per-record]`** marks `/obj/{id}/action` rather than `/obj/action`. Where both exist, the
collection form is the one that takes a list of IDs and is what bulk work should use.

**This lists what the API exposes, not what is safe to call.** Several of these mutate large
amounts of data in one request. Anything write-shaped goes through dedicated bulk-update tooling and its
dry-run-then-apply flow, not straight from here.



## `/accesslevel` — AccessLevel


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `replace` | PUT | `/accesslevel/replace` | `id*`, `replacementID*` |


## `/accessrequest` — AccessRequest


*6 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `grantAccess` | PUT | `/accessrequest/grantAccess` | `accessRequestID`, `actionType`, `forbiddenActions[]` |
| `grantObjectAccess` | PUT | `/accessrequest/grantObjectAccess` | `objCode`, `id`, `accessorID`, `actionType`, `forbiddenActions[]` |
| `ignore` | PUT | `/accessrequest/ignore` | `accessRequestID` |
| `myAccessRequests` | GET | `/accessrequest/myAccessRequests` | `filters` |
| `recall` | PUT | `/accessrequest/recall` | `accessRequestID` |
| `remind` | PUT | `/accessrequest/remind` | `accessRequestID` |


## `/acknowledgement` — Acknowledgement


*3 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `acknowledge` | PUT | `/acknowledgement/acknowledge` | `objCode`, `objID` |
| `acknowledgeMany` | PUT | `/acknowledgement/acknowledgeMany` | `objCodeIDs` |
| `unacknowledge` | PUT | `/acknowledgement/unacknowledge` | `objCode`, `objID` |


## `/agilework` — AgileWork


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `bulkCopy` | PUT | `/agilework/bulkCopy` | `agileWorkIDs[]`, `options[]` |


## `/announcement` — Announcement


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `announcementDraftsForUser` | GET | `/announcement/announcementDraftsForUser` | — |
| `sentAnnouncementsForUser` | GET | `/announcement/sentAnnouncementsForUser` | — |


## `/approval`


*4 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `isInMyApprovals` | PUT | `/approval/isInMyApprovals` | `objectType`, `objectID` |
| `isInMySubmittedApprovals` | PUT | `/approval/isInMySubmittedApprovals` | `objectType`, `objectID` |
| `myApprovals` | GET | `/approval/myApprovals` | `objectType` |
| `mySubmittedApprovals` | GET | `/approval/mySubmittedApprovals` | `objectType` |


## `/assignment` — Assignment


*8 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `assignUserToRoleOnProjects` | PUT | `/assignment/assignUserToRoleOnProjects` | `projectIDs[]`, `swapUserID`, `swapRoleID`, `lockToRole`, `includeIssues` |
| `assignUserToRoleOnTasks` | PUT | `/assignment/assignUserToRoleOnTasks` | `taskIDs[]`, `swapUserID`, `swapRoleID`, `lockToRole`, `includeIssues` |
| `getAssignAssignmentsForTasks` | GET | `/assignment/getAssignAssignmentsForTasks` | `taskIDs[]`, `includeIssues` |
| `getUnassignAssignmentsForTasks` | GET | `/assignment/getUnassignAssignmentsForTasks` | `taskIDs[]`, `includeIssues` |
| `swapUsersOnProjects` | PUT | `/assignment/swapUsersOnProjects` | `projectIDs[]`, `swapToUserID`, `swapFromUserID`, `swapRoleIDs[]`, `lockToRole`, `includeIssues` |
| `swapUsersOnTasks` | PUT | `/assignment/swapUsersOnTasks` | `taskIDs[]`, `swapToUserID`, `swapFromUserID`, `swapRoleIDs[]`, `lockToRole`, `includeIssues` |
| `unassignUserFromProjects` | PUT | `/assignment/unassignUserFromProjects` | `projectIDs[]`, `unassignUserID`, `swapRoleIDs[]`, `includeIssues` |
| `unassignUserFromTasks` | PUT | `/assignment/unassignUserFromTasks` | `taskIDs[]`, `unassignUserID`, `swapRoleIDs[]`, `includeIssues` |


## `/auditloginassession` — AuditLoginAsSession


*4 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `allAccessedUsers` | PUT | `/auditloginassession/allAccessedUsers` | — |
| `allAdmins` | PUT | `/auditloginassession/allAdmins` | — |
| `getAccessedUsers` | PUT | `/auditloginassession/getAccessedUsers` | `userID` |
| `whoAccessedUser` | PUT | `/auditloginassession/whoAccessedUser` | `userID` |


## `/awaitingapproval` — AwaitingApproval


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getMyAwaitingApprovalsFilteredCount` | PUT | `/awaitingapproval/getMyAwaitingApprovalsFilteredCount` | `objectType` |
| `myAwaitingApprovalsFiltered` | GET | `/awaitingapproval/myAwaitingApprovalsFiltered` | `objectType` |


## `/billingrecord` — BillingRecord


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateDataExtension` | PUT | `/billingrecord/calculateDataExtension` | `ID` |


## `/calendarsection` — CalendarSection


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getConcatenatedExpressionForm` | PUT | `/calendarsection/getConcatenatedExpressionForm` | `expression` |
| `getPrettyExpressionForm` | PUT | `/calendarsection/getPrettyExpressionForm` | `expression` |


## `/category` — Category


*11 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `assignCategories` | PUT | `/category/assignCategories` | `objID`, `objCode`, `categoryIDs[]` |
| `assignCategory` | PUT | `/category/assignCategory` | `objID`, `objCode`, `categoryID` |
| `getCascadingRules` | PUT | `/category/getCascadingRules` | `objID`, `objCode`, `categoryIDs[]`, `paramValues`, `isConverting`, `projectID` |
| `isObjectFrozenInPendingApprovalStatus` | PUT | `/category/isObjectFrozenInPendingApprovalStatus` | `objID`, `objCode` |
| `reorderCategories` | PUT | `/category/reorderCategories` | `objID`, `objCode`, `categoryIDs[]` |
| `share` [per-record] | PUT | `/category/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/category/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/category/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/category/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unassignCategories` | PUT | `/category/unassignCategories` | `objID`, `objCode`, `categoryIDs[]` |
| `unassignCategory` | PUT | `/category/unassignCategory` | `objID`, `objCode`, `categoryID` |
| `unshare` [per-record] | PUT | `/category/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/category/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/category/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/category/unsharePublic` | `id*` |


## `/categoryaccessrule` — CategoryAccessRule


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getForObject` | GET | `/categoryaccessrule/getForObject` | `objID`, `objCode` |


## `/classifier` — Classifier


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `activateClassifiers` | PUT | `/classifier/activateClassifiers` | `ids[]` |
| `deactivateClassifiers` | PUT | `/classifier/deactivateClassifiers` | `ids[]` |


## `/company` — Company


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateDataExtension` | PUT | `/company/calculateDataExtension` | `ID` |
| `replace` | PUT | `/company/replace` | `id*`, `replacementID*` |


## `/customenum` — CustomEnum


*26 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getDefaultOpTaskConditionEnum` | PUT | `/customenum/getDefaultOpTaskConditionEnum` | — |
| `getDefaultOpTaskPriorityEnum` | PUT | `/customenum/getDefaultOpTaskPriorityEnum` | — |
| `getDefaultProjectConditionEnum` | PUT | `/customenum/getDefaultProjectConditionEnum` | — |
| `getDefaultProjectStatusEnum` | PUT | `/customenum/getDefaultProjectStatusEnum` | — |
| `getDefaultProjectStatusEnumForGroup` | PUT | `/customenum/getDefaultProjectStatusEnumForGroup` | `groupID` |
| `getDefaultSeverityEnum` | PUT | `/customenum/getDefaultSeverityEnum` | — |
| `getDefaultTaskConditionEnum` | PUT | `/customenum/getDefaultTaskConditionEnum` | — |
| `getDefaultTaskPriorityEnum` | PUT | `/customenum/getDefaultTaskPriorityEnum` | — |
| `getGroupDefaultProjectStatus` | PUT | `/customenum/getGroupDefaultProjectStatus` | `projectID` |
| `getGroupStatuses` | GET | `/customenum/getGroupStatuses` | `groupID`, `includeHidden` |
| `isPossibleToUnlockStatus` | PUT | `/customenum/isPossibleToUnlockStatus` | `type`, `statusKey` |
| `opTaskConditions` | GET | `/customenum/opTaskConditions` | `includeHidden` |
| `opTaskGroupStatuses` | GET | `/customenum/opTaskGroupStatuses` | `opTaskID`, `groupID`, `type`, `includeHidden` |
| `opTaskPriorities` | GET | `/customenum/opTaskPriorities` | `includeHidden` |
| `opTaskSeverities` | GET | `/customenum/opTaskSeverities` | `includeHidden` |
| `opTaskStatuses` | GET | `/customenum/opTaskStatuses` | `type`, `includeHidden` |
| `opTaskTypes` | GET | `/customenum/opTaskTypes` | — |
| `projectConditions` | GET | `/customenum/projectConditions` | `includeHidden` |
| `projectGroupStatuses` | GET | `/customenum/projectGroupStatuses` | `projectID`, `groupID`, `includeHidden` |
| `projectPriorities` | GET | `/customenum/projectPriorities` | `includeHidden` |
| `projectStatuses` | GET | `/customenum/projectStatuses` | `includeHidden` |
| `taskConditions` | GET | `/customenum/taskConditions` | `includeHidden` |
| `taskGroupStatuses` | GET | `/customenum/taskGroupStatuses` | `taskID`, `groupID`, `includeHidden` |
| `taskPriorities` | GET | `/customenum/taskPriorities` | `includeHidden` |
| `taskStatuses` | GET | `/customenum/taskStatuses` | `includeHidden` |
| `templatetaskPriorities` | GET | `/customenum/templatetaskPriorities` | `includeHidden` |


## `/customer`


*5 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getPackagingOptionValue` | PUT | `/customer/getPackagingOptionValue` | `option` |
| `goalsEnabled` | PUT | `/customer/goalsEnabled` | — |
| `isPackagingOptionEnabled` | PUT | `/customer/isPackagingOptionEnabled` | `option` |
| `productEnabled` | PUT | `/customer/productEnabled` | `product` |
| `updateLoginAsSettings` | PUT | `/customer/updateLoginAsSettings` | `customer` |


## `/customerpreferences` — CustomerPreferences


*3 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getIsAutoUpgradeDisabled` | PUT | `/customerpreferences/getIsAutoUpgradeDisabled` | — |
| `getTimesheetPreferences` | PUT | `/customerpreferences/getTimesheetPreferences` | — |
| `setTimesheetPreferences` | PUT | `/customerpreferences/setTimesheetPreferences` | `preferences` |


## `/customlabel` — CustomLabel


*5 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `checkDelete` | PUT | `/customlabel/checkDelete` | `id`, `layoutTemplateID` |
| `customLabels` | GET | `/customlabel/customLabels` | — |
| `inUseByOtherLayoutTemplates` | PUT | `/customlabel/inUseByOtherLayoutTemplates` | `id`, `layoutTemplateID` |
| `removeCustomLabel` | PUT | `/customlabel/removeCustomLabel` | `id`, `layoutTemplateID` |
| `usedCustomLabels` | GET | `/customlabel/usedCustomLabels` | — |


## `/docmetadatalinkgroup` — DocMetadataLinkGroup


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getMetadataDetailsForDocument` | PUT | `/docmetadatalinkgroup/getMetadataDetailsForDocument` | `documentID`, `externalIntegrationType`, `documentProviderID` |
| `getMetadataForDocument` | PUT | `/docmetadatalinkgroup/getMetadataForDocument` | `documentID`, `externalIntegrationType`, `documentProviderID` |


## `/document` — Document


*23 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateDataExtension` | PUT | `/document/calculateDataExtension` | `ID` |
| `checkIn` | PUT | `/document/checkIn` | `documentIDs[]` |
| `checkOut` | PUT | `/document/checkOut` | `documentIDs[]` |
| `completeLargeDocument` | PUT | `/document/completeLargeDocument` | `uploadID`, `key`, `eTagMap`, `name`, `docObjCode`, `docObjID`, `documentID`, `fileType`, `folderID`, `createProof`, `interactive`, `advancedProofingOptions`, `proofID`, `proofToken` |
| `createLargeDocument` | PUT | `/document/createLargeDocument` | `fileSize`, `documentID`, `folderID` |
| `createLinkedProofVersion` | PUT | `/document/createLinkedProofVersion` | `documentID`, `fileHandle`, `fileName`, `creatorName` |
| `createProof` | PUT | `/document/createProof` | `documentVersionID`, `advancedProofingOptions` |
| `createProofRest` | PUT | `/document/createProofRest` | `documentVersionID`, `advancedProofingOptions` |
| `getDocumentProofTemplate` | PUT | `/document/getDocumentProofTemplate` | `proofToken` |
| `getProofRecipients` | PUT | `/document/getProofRecipients` | `templateId`, `stageId` |
| `getProofStages` | PUT | `/document/getProofStages` | `templateId` |
| `getProofTemplate` | PUT | `/document/getProofTemplate` | — |
| `getTotalSizeForDocuments` | PUT | `/document/getTotalSizeForDocuments` | `documentIDs[]`, `includeLinked` |
| `isLinkedDocument` | PUT | `/document/isLinkedDocument` | `documentID` |
| `isProofAutoGenrationEnabled` | PUT | `/document/isProofAutoGenrationEnabled` | — |
| `move` | PUT | `/document/move` | `ID`, `objID`, `docObjCode` |
| `moveToFolder` | PUT | `/document/moveToFolder` | `documentIDs[]`, `folderID` |
| `sendDocumentsToExternalProvider` | PUT | `/document/sendDocumentsToExternalProvider` | `documentIDs[]`, `providerID`, `destinationFolderID`, `metadata` |
| `share` [per-record] | PUT | `/document/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/document/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/document/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/document/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unlinkDocuments` | PUT | `/document/unlinkDocuments` | `ids[]` |
| `unshare` [per-record] | PUT | `/document/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/document/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/document/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/document/unsharePublic` | `id*` |


## `/documentfolder` — DocumentFolder


*9 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getFolderSizeInBytes` | PUT | `/documentfolder/getFolderSizeInBytes` | `folderID`, `recursive`, `includeLinked` |
| `isLinkedFolder` | PUT | `/documentfolder/isLinkedFolder` | `documentFolderID` |
| `isSmartFolder` | PUT | `/documentfolder/isSmartFolder` | `documentFolderID` |
| `myFolders` | GET | `/documentfolder/myFolders` | — |
| `share` [per-record] | PUT | `/documentfolder/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/documentfolder/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/documentfolder/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/documentfolder/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unlinkFolders` | PUT | `/documentfolder/unlinkFolders` | `ids[]` |
| `unshare` [per-record] | PUT | `/documentfolder/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/documentfolder/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/documentfolder/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/documentfolder/unsharePublic` | `id*` |


## `/documentversion` — DocumentVersion


*3 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getDocumentReviewerDecision` | PUT | `/documentversion/getDocumentReviewerDecision` | `documentVersionID` |
| `getProofingTokens` | PUT | `/documentversion/getProofingTokens` | `versionID` |
| `setDocumentReviewerDecision` | PUT | `/documentversion/setDocumentReviewerDecision` | `documentVersionID`, `reviewerDecision`, `comment` |


## `/endorsement` — Endorsement


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `like` | PUT | `/endorsement/like` | `ID` |
| `unlike` | PUT | `/endorsement/unlike` | `ID` |


## `/ewsfilehandle`


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `upload` | GET | `/ewsfilehandle/upload` | `uploadInfo` |


## `/exchangerate` — ExchangeRate


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getCustomerCurrencies` | PUT | `/exchangerate/getCustomerCurrencies` | — |
| `saveCustomerExchangeRates` | PUT | `/exchangerate/saveCustomerExchangeRates` | `baseCurrency`, `rates` |


## `/expense` — Expense


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateDataExtension` | PUT | `/expense/calculateDataExtension` | `ID` |
| `move` | PUT | `/expense/move` | `ID`, `objID`, `expObjCode` |


## `/expensetype` — ExpenseType


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `replace` | PUT | `/expensetype/replace` | `id*`, `replacementID*` |


## `/externaldocument`


*9 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `browseList` | GET | `/externaldocument/browseList` | `filters`, `providerType`, `documentProviderID`, `searchParams` |
| `browseListWithLinkAction` | PUT | `/externaldocument/browseListWithLinkAction` | `providerType`, `documentProviderID`, `searchParams`, `loadBreadcrumbs`, `linkAction` |
| `getDocumentDownloadUrl` | PUT | `/externaldocument/getDocumentDownloadUrl` | `providerType`, `documentProviderID`, `documentID`, `isOpen` |
| `getFolderMetaData` | GET | `/externaldocument/getFolderMetaData` | `providerType`, `documentProviderID`, `folderID`, `isForLinkedFolder` |
| `getRootFolderID` | PUT | `/externaldocument/getRootFolderID` | `providerType`, `documentProviderID` |
| `getRootFolderIDFromDB` | PUT | `/externaldocument/getRootFolderIDFromDB` | `documentProviderID` |
| `linkExternalDocumentObjects` | PUT | `/externaldocument/linkExternalDocumentObjects` | `refObjCode`, `refObjID`, `providerType`, `documentProviderID`, `objects`, `destFolderID`, `advancedProofingOptions` |
| `searchExternalDocuments` | GET | `/externaldocument/searchExternalDocuments` | `providerType`, `documentProviderID`, `searchString`, `limit`, `offset`, `searchInFolder` |
| `setLinkedFolderMetadata` | PUT | `/externaldocument/setLinkedFolderMetadata` | `documentProviderID`, `providerType`, `externalStorageID`, `projectID` |


## `/externalsection` — ExternalSection


*4 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateIframeURL` | PUT | `/externalsection/calculateIframeURL` | `externalSectionID`, `objCode`, `objID` |
| `calculateIframeURLS` | PUT | `/externalsection/calculateIframeURLS` | `externalSectionIDs[]`, `objCode`, `objID` |
| `calculateURL` | PUT | `/externalsection/calculateURL` | `externalSectionID`, `objCode`, `objID` |
| `calculateURLS` | PUT | `/externalsection/calculateURLS` | `externalSectionIDs[]`, `objCode`, `objID` |


## `/group` — Group


*18 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `addRemoveLicenseTypeLimits` | PUT | `/group/addRemoveLicenseTypeLimits` | `addGroupIDs[]`, `removeGroupIDs[]` |
| `addSubgroups` | PUT | `/group/addSubgroups` | `ID`, `newSubgroupIDs[]` |
| `assignMultiple` | PUT | `/group/assignMultiple` | `ID`, `userIDs[]`, `roleIDs[]`, `teamID` |
| `calculateDataExtension` | PUT | `/group/calculateDataExtension` | `ID` |
| `checkDelete` | PUT | `/group/checkDelete` | `ids[]` |
| `completeGroupInfo` | PUT | `/group/completeGroupInfo` | `groupId` |
| `getGroupMembers` | PUT | `/group/getGroupMembers` | `ID` |
| `getParents` | PUT | `/group/getParents` | `ID` |
| `linkExternalObject` | PUT | `/group/linkExternalObject` | `objID`, `linkedObjectID`, `integrationType`, `URL`, `params[]` |
| `replace` | PUT | `/group/replace` | `id*`, `replacementID*` |
| `replaceDeleteGroups` | PUT | `/group/replaceDeleteGroups` | `ids[]`, `replaceGroupID` |
| `setLicenseTypeLimit` | PUT | `/group/setLicenseTypeLimit` | `groupID`, `licenseType`, `ltLimit` |
| `share` [per-record] | PUT | `/group/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/group/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/group/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/group/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unlinkExternalObject` | PUT | `/group/unlinkExternalObject` | `objID`, `linkedObjectID`, `integrationType` |
| `unshare` [per-record] | PUT | `/group/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/group/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/group/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/group/unsharePublic` | `id*` |
| `updateMembersList` | PUT | `/group/updateMembersList` | `ID`, `newMemberIDs[]`, `removedMemberIDs[]` |


## `/hour` — Hour


*3 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `approve` | PUT | `/hour/approve` | `hourID` |
| `calculateDataExtension` | PUT | `/hour/calculateDataExtension` | `ID` |
| `unapprove` | PUT | `/hour/unapprove` | `hourID`, `comment` |


## `/hourtype` — HourType


*6 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `defaultOpTaskHourType` | GET | `/hourtype/defaultOpTaskHourType` | — |
| `defaultProjectHourType` | GET | `/hourtype/defaultProjectHourType` | — |
| `defaultTaskHourType` | GET | `/hourtype/defaultTaskHourType` | — |
| `globalHourTypes` | GET | `/hourtype/globalHourTypes` | — |
| `objectHourTypes` | GET | `/hourtype/objectHourTypes` | `objCode`, `objID`, `userID` |
| `replace` | PUT | `/hourtype/replace` | `id*`, `replacementID*` |


## `/iteration` — Iteration


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `moveIssues` | PUT | `/iteration/moveIssues` | `iterationID`, `teamID`, `issueIDs[]` |
| `moveStories` | PUT | `/iteration/moveStories` | `iterationID`, `teamID`, `storyIDs[]` |


## `/journalentry` — JournalEntry


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `like` | PUT | `/journalentry/like` | `ID` |
| `unlike` | PUT | `/journalentry/unlike` | `ID` |


## `/note` — Note


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `like` | PUT | `/note/like` | `ID` |
| `unlike` | PUT | `/note/unlike` | `ID` |


## `/objectcategory` — ObjectCategory


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getForObject` | GET | `/objectcategory/getForObject` | `objID`, `objCode` |


## `/optask` — OpTask


*27 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `acceptWork` | PUT | `/optask/acceptWork` | `ID`, `status` |
| `approveApproval` | PUT | `/optask/approveApproval` | `ID`, `userID`, `username`, `password`, `auditNote`, `auditUserIDs[]`, `sendNoteAsEmail` |
| `assign` | PUT | `/optask/assign` | `ID`, `objID`, `objCode` |
| `assignMultiple` | PUT | `/optask/assignMultiple` | `ID`, `userIDs[]`, `roleIDs[]`, `teamIDs[]`, `teamID` |
| `bulkMove` | PUT | `/optask/bulkMove` | `issueIDs[]`, `projectID`, `parentID` |
| `bulkMoveWithOptions` | PUT | `/optask/bulkMoveWithOptions` | `IDs[]`, `projectID`, `parentID`, `newName`, `options[]` |
| `calculateDataExtension` | PUT | `/optask/calculateDataExtension` | `ID` |
| `convertToProject` | PUT | `/optask/convertToProject` | `ID`, `project`, `exchangeRate`, `options[]`, `copyNativeFields`, `copyCategories` |
| `convertToTask` | PUT | `/optask/convertToTask` | `ID`, `task`, `options[]`, `copyNativeFields`, `copyCategories` |
| `copyIssue` | PUT | `/optask/copyIssue` | `opTaskID`, `name`, `description`, `projectID`, `options`, `parentID` |
| `defaultShownTimesheetIssues` | GET | `/optask/defaultShownTimesheetIssues` | `timesheetID` |
| `getRequestPath` | PUT | `/optask/getRequestPath` | `queueDef`, `queueTopicID` |
| `linkExternalObject` | PUT | `/optask/linkExternalObject` | `objID`, `linkedObjectID`, `integrationType`, `URL`, `params[]` |
| `markDone` | PUT | `/optask/markDone` | `ID`, `status` |
| `markNotDone` | PUT | `/optask/markNotDone` | `ID`, `assignmentID` |
| `move` | PUT | `/optask/move` | `ID`, `projectID` |
| `moveToTask` | PUT | `/optask/moveToTask` | `ID`, `projectID`, `parentID` |
| `recallApproval` | PUT | `/optask/recallApproval` | `ID` |
| `rejectApproval` | PUT | `/optask/rejectApproval` | `ID`, `userID`, `username`, `password`, `auditNote`, `auditUserIDs[]`, `sendNoteAsEmail` |
| `replyToAssignment` | PUT | `/optask/replyToAssignment` | `ID`, `noteText`, `commitDate` |
| `share` [per-record] | PUT | `/optask/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/optask/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/optask/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/optask/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unacceptWork` | PUT | `/optask/unacceptWork` | `ID`, `status` |
| `unassign` | PUT | `/optask/unassign` | `ID`, `userID` |
| `unlinkExternalObject` | PUT | `/optask/unlinkExternalObject` | `objID`, `linkedObjectID`, `integrationType` |
| `unshare` [per-record] | PUT | `/optask/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/optask/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/optask/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/optask/unsharePublic` | `id*` |


## `/parameter` — Parameter


*4 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `share` [per-record] | PUT | `/parameter/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/parameter/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/parameter/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/parameter/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unshare` [per-record] | PUT | `/parameter/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/parameter/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/parameter/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/parameter/unsharePublic` | `id*` |


## `/portalsection` — PortalSection


*11 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `exportFusionChartToPDF` | PUT | `/portalsection/exportFusionChartToPDF` | `pngByteArray[]`, `fileName`, `reportName` |
| `getPK` | PUT | `/portalsection/getPK` | `objCode` |
| `getReportAsUser` | GET | `/portalsection/getReportAsUser` | `userID`, `ID` |
| `getReportFromCache` | PUT | `/portalsection/getReportFromCache` | `backgroundJobID` |
| `isReportFilterable` | PUT | `/portalsection/isReportFilterable` | `queryClassObjCode`, `objCode`, `objID` |
| `linkCustomer` | PUT | `/portalsection/linkCustomer` | `ID` |
| `share` [per-record] | PUT | `/portalsection/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/portalsection/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/portalsection/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/portalsection/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unlinkCustomer` | PUT | `/portalsection/unlinkCustomer` | `ID` |
| `unshare` [per-record] | PUT | `/portalsection/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/portalsection/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/portalsection/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/portalsection/unsharePublic` | `id*` |


## `/portaltab` — PortalTab


*6 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `advancedCopy` | PUT | `/portaltab/advancedCopy` | `ID`, `newName`, `advancedCopies` |
| `exportDashboard` | PUT | `/portaltab/exportDashboard` | `ID`, `dashboardExports[]`, `dashboardExportOptions` |
| `share` [per-record] | PUT | `/portaltab/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/portaltab/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/portaltab/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/portaltab/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unshare` [per-record] | PUT | `/portaltab/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/portaltab/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/portaltab/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/portaltab/unsharePublic` | `id*` |


## `/portfolio` — Portfolio


*7 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateDataExtension` | PUT | `/portfolio/calculateDataExtension` | `ID` |
| `linkExternalObject` | PUT | `/portfolio/linkExternalObject` | `objID`, `linkedObjectID`, `integrationType`, `URL`, `params[]` |
| `share` [per-record] | PUT | `/portfolio/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/portfolio/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/portfolio/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/portfolio/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unlinkExternalObject` | PUT | `/portfolio/unlinkExternalObject` | `objID`, `linkedObjectID`, `integrationType` |
| `unshare` [per-record] | PUT | `/portfolio/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/portfolio/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/portfolio/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/portfolio/unsharePublic` | `id*` |


## `/program` — Program


*8 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateDataExtension` | PUT | `/program/calculateDataExtension` | `ID` |
| `linkExternalObject` | PUT | `/program/linkExternalObject` | `objID`, `linkedObjectID`, `integrationType`, `URL`, `params[]` |
| `move` | PUT | `/program/move` | `ID`, `portfolioID`, `options[]` |
| `share` [per-record] | PUT | `/program/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/program/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/program/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/program/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unlinkExternalObject` | PUT | `/program/unlinkExternalObject` | `objID`, `linkedObjectID`, `integrationType` |
| `unshare` [per-record] | PUT | `/program/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/program/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/program/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/program/unsharePublic` | `id*` |


## `/project` — Project


*18 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `approveApproval` | PUT | `/project/approveApproval` | `ID`, `userID`, `approvalUsername`, `approvalPassword`, `auditNote`, `auditUserIDs[]`, `sendNoteAsEmail` |
| `attachTemplate` | PUT | `/project/attachTemplate` | `ID`, `templateID`, `predecessorTaskID`, `parentTaskID`, `excludeTemplateTaskIDs[]`, `options[]` |
| `calculateDataExtension` | PUT | `/project/calculateDataExtension` | `ID` |
| `calculateFinance` | PUT | `/project/calculateFinance` | `ID` |
| `calculateTimeline` | PUT | `/project/calculateTimeline` | `ID` |
| `createProjectWithOverride` | PUT | `/project/createProjectWithOverride` | `project`, `exchangeRate` |
| `defaultShownTimesheetProjects` | GET | `/project/defaultShownTimesheetProjects` | `timesheetID` |
| `helpDeskQueues` | GET | `/project/helpDeskQueues` | `filters` |
| `linkExternalObject` | PUT | `/project/linkExternalObject` | `objID`, `linkedObjectID`, `integrationType`, `URL`, `params[]` |
| `recallApproval` | PUT | `/project/recallApproval` | `ID` |
| `recentHelpDeskQueues` | GET | `/project/recentHelpDeskQueues` | `filters` |
| `rejectApproval` | PUT | `/project/rejectApproval` | `ID`, `userID`, `approvalUsername`, `approvalPassword`, `auditNote`, `auditUserIDs[]`, `sendNoteAsEmail` |
| `share` [per-record] | PUT | `/project/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/project/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/project/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/project/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unlinkExternalObject` | PUT | `/project/unlinkExternalObject` | `objID`, `linkedObjectID`, `integrationType` |
| `unshare` [per-record] | PUT | `/project/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/project/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/project/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/project/unsharePublic` | `id*` |
| `updateBusinessCaseSource` | PUT | `/project/updateBusinessCaseSource` | `projectID`, `source` |


## `/queuedef` — QueueDef


*3 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getQueueDefTree` | PUT | `/queuedef/getQueueDefTree` | `name` |
| `queueTopics` | GET | `/queuedef/queueTopics` | `filters` |
| `searchByPath` | PUT | `/queuedef/searchByPath` | `name`, `limit` |


## `/queuetopic` — QueueTopic


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `queueTopicByID` | GET | `/queuetopic/queueTopicByID` | `queueTopicID` |


## `/queuetopicgroup` — QueueTopicGroup


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `queueTopicGroups` | GET | `/queuetopicgroup/queueTopicGroups` | `filters` |


## `/rate` — Rate


*6 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `createRates` | PUT | `/rate/createRates` | `rates[]` |
| `deleteRateForRole` | PUT | `/rate/deleteRateForRole` | `attachableID`, `attachableObjCode`, `rateID` |
| `editRatesForRole` | PUT | `/rate/editRatesForRole` | `attachableID`, `attachableObjCode`, `roleID`, `rates[]`, `currencyCode`, `initialClassifierID`, `classifierID` |
| `getUsedClassifierIds` | PUT | `/rate/getUsedClassifierIds` | `rateCardID`, `roleID`, `objID`, `objCode` |
| `setRatesForObject` | PUT | `/rate/setRatesForObject` | `attachableID`, `attachableObjCode`, `rates[]` |
| `setRatesForRole` | PUT | `/rate/setRatesForRole` | `attachableID`, `attachableObjCode`, `roleID`, `rates[]`, `currencyCode`, `classifierID` |


## `/recent` — Recent


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `updateLastViewedObject` | PUT | `/recent/updateLastViewedObject` | `ID` |


## `/resourceplannerfilter` — ResourcePlannerFilter


*4 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `share` [per-record] | PUT | `/resourceplannerfilter/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/resourceplannerfilter/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/resourceplannerfilter/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/resourceplannerfilter/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unshare` [per-record] | PUT | `/resourceplannerfilter/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/resourceplannerfilter/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/resourceplannerfilter/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/resourceplannerfilter/unsharePublic` | `id*` |


## `/risktype` — RiskType


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `replace` | PUT | `/risktype/replace` | `id*`, `replacementID*` |


## `/role` — Role


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `replace` | PUT | `/role/replace` | `id*`, `replacementID*` |


## `/schedule` — Schedule


*6 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `defaultSchedule` | GET | `/schedule/defaultSchedule` | — |
| `getEarliestWorkTimeOfDay` | PUT | `/schedule/getEarliestWorkTimeOfDay` | `ID`, `date` |
| `getLatestWorkTimeOfDay` | PUT | `/schedule/getLatestWorkTimeOfDay` | `ID`, `date` |
| `getNextCompletionDate` | PUT | `/schedule/getNextCompletionDate` | `ID`, `date`, `costInMinutes` |
| `getNextStartDate` | PUT | `/schedule/getNextStartDate` | `ID`, `date` |
| `replace` | PUT | `/schedule/replace` | `id*`, `replacementID*` |


## `/scheduledreport` — ScheduledReport


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `sendReportDeliveryNow` | PUT | `/scheduledreport/sendReportDeliveryNow` | `userIDs[]`, `teamIDs[]`, `groupIDs[]`, `roleIDs[]`, `externalEmails`, `deliveryOptions` |


## `/subscribe` — Subscribe


*5 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `addSubscribers` | PUT | `/subscribe/addSubscribers` | `userIDs[]`, `objID`, `objCode` |
| `removeSubscribers` | PUT | `/subscribe/removeSubscribers` | `userIDs[]`, `objID`, `objCode` |
| `subscribers` | GET | `/subscribe/subscribers` | `objID`, `objCode` |
| `subscribes` | PUT | `/subscribe/subscribes` | `objIDs[]`, `objCodes[]` |
| `unsubscribes` | PUT | `/subscribe/unsubscribes` | `objIDs[]`, `objCodes[]` |


## `/task` — Task


*26 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `acceptWork` | PUT | `/task/acceptWork` | `ID`, `status` |
| `allTasksOnIterations` | GET | `/task/allTasksOnIterations` | `iterationIDs[]` |
| `approveApproval` | PUT | `/task/approveApproval` | `ID`, `userID`, `username`, `password`, `auditNote`, `auditUserIDs[]`, `sendNoteAsEmail` |
| `assign` | PUT | `/task/assign` | `ID`, `objID`, `objCode` |
| `assignMultiple` | PUT | `/task/assignMultiple` | `ID`, `userIDs[]`, `roleIDs[]`, `teamIDs[]`, `teamID` |
| `bulkCopy` | PUT | `/task/bulkCopy` | `taskIDs[]`, `projectID`, `parentID`, `options[]` |
| `bulkMove` | PUT | `/task/bulkMove` | `taskIDs[]`, `projectID`, `parentID`, `options[]` |
| `calculateDataExtension` | PUT | `/task/calculateDataExtension` | `ID` |
| `calculateDataExtensions` | PUT | `/task/calculateDataExtensions` | `ids[]` |
| `convertToProject` | PUT | `/task/convertToProject` | `ID`, `project`, `exchangeRate`, `copyCategories` |
| `defaultShownTimesheetTasks` | GET | `/task/defaultShownTimesheetTasks` | `timesheetID` |
| `linkExternalObject` | PUT | `/task/linkExternalObject` | `objID`, `linkedObjectID`, `integrationType`, `URL`, `params[]` |
| `markDone` | PUT | `/task/markDone` | `ID`, `status` |
| `markNotDone` | PUT | `/task/markNotDone` | `ID`, `assignmentID` |
| `move` | PUT | `/task/move` | `ID`, `projectID`, `parentID`, `options[]` |
| `recallApproval` | PUT | `/task/recallApproval` | `ID` |
| `rejectApproval` | PUT | `/task/rejectApproval` | `ID`, `userID`, `username`, `password`, `auditNote`, `auditUserIDs[]`, `sendNoteAsEmail` |
| `replyToAssignment` | PUT | `/task/replyToAssignment` | `ID`, `noteText`, `commitDate` |
| `share` [per-record] | PUT | `/task/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/task/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/task/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/task/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unacceptWork` | PUT | `/task/unacceptWork` | `ID`, `status` |
| `unassign` | PUT | `/task/unassign` | `ID`, `userID` |
| `unassignOccurrences` | PUT | `/task/unassignOccurrences` | `ID`, `userID` |
| `unlinkExternalObject` | PUT | `/task/unlinkExternalObject` | `objID`, `linkedObjectID`, `integrationType` |
| `unshare` [per-record] | PUT | `/task/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/task/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/task/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/task/unsharePublic` | `id*` |


## `/template` — Template


*6 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `calculateDataExtension` | PUT | `/template/calculateDataExtension` | `ID` |
| `calculateTimeline` | PUT | `/template/calculateTimeline` | `ID` |
| `share` [per-record] | PUT | `/template/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/template/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/template/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/template/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unshare` [per-record] | PUT | `/template/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/template/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/template/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/template/unsharePublic` | `id*` |


## `/templatetask` — TemplateTask


*4 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `bulkCopy` | PUT | `/templatetask/bulkCopy` | `templateID`, `templateTaskIDs[]`, `parentTemplateTaskID`, `options[]` |
| `bulkMove` | PUT | `/templatetask/bulkMove` | `templateTaskIDs[]`, `templateID`, `parentID`, `options[]` |
| `calculateDataExtension` | PUT | `/templatetask/calculateDataExtension` | `ID` |
| `move` | PUT | `/templatetask/move` | `ID`, `templateID`, `parentID`, `options[]` |


## `/timesheetprofile` — TimesheetProfile


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `replace` | PUT | `/timesheetprofile/replace` | `id*`, `replacementID*` |


## `/uifilter` — UIFilter


*8 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `addJoinForNullableFields` | PUT | `/uifilter/addJoinForNullableFields` | `objCode`, `filterMap` |
| `disableSystemWideVisibility` | PUT | `/uifilter/disableSystemWideVisibility` | `filterIDs[]` |
| `enableSystemWideVisibility` | PUT | `/uifilter/enableSystemWideVisibility` | `filterIDs[]` |
| `filtersForObjCode` | GET | `/uifilter/filtersForObjCode` | `objCode`, `filterType` |
| `share` [per-record] | PUT | `/uifilter/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/uifilter/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/uifilter/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/uifilter/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unshare` [per-record] | PUT | `/uifilter/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/uifilter/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/uifilter/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/uifilter/unsharePublic` | `id*` |


## `/uigroupby` — UIGroupBy


*6 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `disableSystemWideVisibility` | PUT | `/uigroupby/disableSystemWideVisibility` | `groupByIDs[]` |
| `enableSystemWideVisibility` | PUT | `/uigroupby/enableSystemWideVisibility` | `groupByIDs[]` |
| `share` [per-record] | PUT | `/uigroupby/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/uigroupby/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/uigroupby/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/uigroupby/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unshare` [per-record] | PUT | `/uigroupby/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/uigroupby/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/uigroupby/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/uigroupby/unsharePublic` | `id*` |


## `/uitemplate` — UITemplate


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `migrateCustomersAllLayoutTemplates` | PUT | `/uitemplate/migrateCustomersAllLayoutTemplates` | `overrideIfExists` |
| `migrateLayoutTemplates` | PUT | `/uitemplate/migrateLayoutTemplates` | `layoutTemplateIDs[]`, `overrideIfExists` |


## `/uiview` — UIView


*7 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `disableSystemWideVisibility` | PUT | `/uiview/disableSystemWideVisibility` | `viewIDs[]` |
| `enableSystemWideVisibility` | PUT | `/uiview/enableSystemWideVisibility` | `viewIDs[]` |
| `share` [per-record] | PUT | `/uiview/{id}/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `share` | PUT | `/uiview/share` | `id*`, `accessorObjCode*`, `accessorID*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` [per-record] | PUT | `/uiview/{id}/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `sharePublic` | PUT | `/uiview/sharePublic` | `id*`, `coreAction*`, `forbiddenActions[]` |
| `unshare` [per-record] | PUT | `/uiview/{id}/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unshare` | PUT | `/uiview/unshare` | `id*`, `accessorObjCode*`, `accessorID*` |
| `unsharePublic` [per-record] | PUT | `/uiview/{id}/unsharePublic` | `id*` |
| `unsharePublic` | PUT | `/uiview/unsharePublic` | `id*` |
| `viewsForObjCode` | GET | `/uiview/viewsForObjCode` | `objCode` |


## `/update`


*12 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `auditSession` | GET | `/update/auditSession` | `filters`, `userID`, `targetUserID`, `startDate`, `endDate`, `pageNumber` |
| `auditSessionCount` | PUT | `/update/auditSessionCount` | `userID`, `targetUserID`, `startDate`, `endDate` |
| `endorsementUpdates` | GET | `/update/endorsementUpdates` | `filters`, `userID` |
| `objectUpdates` | GET | `/update/objectUpdates` | `filters`, `objCode`, `objID`, `sinceDate` |
| `objectUpdatesByCommentID` | GET | `/update/objectUpdatesByCommentID` | `objCode`, `objID`, `commentID` |
| `objectUpdatesMobile` | GET | `/update/objectUpdatesMobile` | `filters`, `objCode`, `objID`, `sinceDate` |
| `objectUpdatesWithNoteAndJournalEntryIndex` | GET | `/update/objectUpdatesWithNoteAndJournalEntryIndex` | `filters`, `objCode`, `objID`, `sinceDate`, `firstNote`, `firstJournalEntry` |
| `recentUpdates` | GET | `/update/recentUpdates` | `filters`, `sinceDate` |
| `recentUpdatesObjIDs` | PUT | `/update/recentUpdatesObjIDs` | — |
| `updateThread` | GET | `/update/updateThread` | `noteID` |
| `updateThreadMobile` | GET | `/update/updateThreadMobile` | `noteID` |
| `updates` | GET | `/update/updates` | `filters`, `streamType` |


## `/user` — User


*22 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `addMobileDevice` | PUT | `/user/addMobileDevice` | `token`, `deviceType` |
| `assignUserToken` | PUT | `/user/assignUserToken` | `ID` |
| `calculateDataExtension` | PUT | `/user/calculateDataExtension` | `ID` |
| `clearAllApiKeys` | PUT | `/user/clearAllApiKeys` | — |
| `clearApiKey` | PUT | `/user/clearApiKey` | — |
| `completeUserRegistration` | PUT | `/user/completeUserRegistration` | `ID`, `firstName`, `lastName`, `token`, `title`, `newPassword` |
| `generateApiKey` | PUT | `/user/generateApiKey` | — |
| `getApiKey` | PUT | `/user/getApiKey` | `ID` |
| `getAvailableActions` | PUT | `/user/getAvailableActions` | `objCode` |
| `getUserAccessPermissionsByObjCode` | PUT | `/user/getUserAccessPermissionsByObjCode` | `ids`, `objCode` |
| `getUserCustomLabels` | PUT | `/user/getUserCustomLabels` | — |
| `getUsersAvailableTime` | PUT | `/user/getUsersAvailableTime` | `userIDs[]`, `fromDate`, `toDate` |
| `hasAnyAccess` | PUT | `/user/hasAnyAccess` | `objCode`, `actionType` |
| `hasGrantLoginAsAccess` | PUT | `/user/hasGrantLoginAsAccess` | `ID` |
| `isUserAdmin` | PUT | `/user/isUserAdmin` | `userID`, `adminID` |
| `isUserTerminologyActive` | PUT | `/user/isUserTerminologyActive` | — |
| `removeMobileDevice` | PUT | `/user/removeMobileDevice` | `token` |
| `replace` | PUT | `/user/replace` | `id*`, `replacementID*` |
| `resetRopgPassword` | PUT | `/user/resetRopgPassword` | `newPassword` |
| `sendInvitationEmail` | PUT | `/user/sendInvitationEmail` | `ID` |
| `shouldShowProofHQNavButton` | PUT | `/user/shouldShowProofHQNavButton` | — |
| `userAdmins` | GET | `/user/userAdmins` | `filters` |


## `/userapproval` — UserApproval


*2 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `approve` | PUT | `/userapproval/approve` | `userIDs[]` |
| `reject` | PUT | `/userapproval/reject` | `userIDs[]` |


## `/usernote` — UserNote


*18 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `acknowledge` | PUT | `/usernote/acknowledge` | `ID` |
| `acknowledgeAll` | PUT | `/usernote/acknowledgeAll` | — |
| `acknowledgeMany` | PUT | `/usernote/acknowledgeMany` | `objIDs[]` |
| `acknowledgeMyNotifications` | PUT | `/usernote/acknowledgeMyNotifications` | `objIDs[]` |
| `announcementNotifications` | GET | `/usernote/announcementNotifications` | `pageNumber` |
| `deletedAnnouncementNotes` | GET | `/usernote/deletedAnnouncementNotes` | `limit` |
| `myAllObjectTypesUnreadNotifications` | GET | `/usernote/myAllObjectTypesUnreadNotifications` | `limit`, `first`, `includeAll` |
| `myNewestAnnouncementNotification` | GET | `/usernote/myNewestAnnouncementNotification` | — |
| `myNewestNotification` | GET | `/usernote/myNewestNotification` | — |
| `myNotifications` | GET | `/usernote/myNotifications` | `filters` |
| `myNotificationsQuickList` | GET | `/usernote/myNotificationsQuickList` | — |
| `myUnreadAnnouncementNotifications` | GET | `/usernote/myUnreadAnnouncementNotifications` | `limit` |
| `myUnreadNotifications` | GET | `/usernote/myUnreadNotifications` | `limit` |
| `unacknowledge` | PUT | `/usernote/unacknowledge` | `ID` |
| `unacknowledgeMany` | PUT | `/usernote/unacknowledgeMany` | `objIDs[]` |
| `unacknowledgedAllObjectTypesCount` | PUT | `/usernote/unacknowledgedAllObjectTypesCount` | — |
| `unacknowledgedAnnouncementCount` | PUT | `/usernote/unacknowledgedAnnouncementCount` | — |
| `unacknowledgedCount` | PUT | `/usernote/unacknowledgedCount` | — |


## `/work` — Work


*19 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `getMyAccomplishmentsCount` | PUT | `/work/getMyAccomplishmentsCount` | — |
| `getMyWorkCount` | PUT | `/work/getMyWorkCount` | — |
| `getMyWorkCountFiltered` | PUT | `/work/getMyWorkCountFiltered` | `filters` |
| `getWFHomeObjects` | PUT | `/work/getWFHomeObjects` | `show`, `view`, `search`, `first`, `limit`, `startDate`, `endDate`, `actionGroup` |
| `getWFHomeObjectsFilterSortBy` | PUT | `/work/getWFHomeObjectsFilterSortBy` | `filter`, `sortBy`, `search`, `first`, `limit`, `isAscending`, `includeUndated`, `startDate`, `endDate` |
| `getWFHomeObjectsListWithoutDate` | PUT | `/work/getWFHomeObjectsListWithoutDate` | `filter`, `sortBy`, `first`, `limit`, `isAscending` |
| `getWFHomeObjectsProjectItemList` | PUT | `/work/getWFHomeObjectsProjectItemList` | `filter`, `projectID`, `search`, `first`, `limit`, `isAscending`, `includeUndated`, `startDate`, `endDate` |
| `getWFHomeObjectsProjectList` | PUT | `/work/getWFHomeObjectsProjectList` | `filter`, `isAscending`, `includeUndated`, `search`, `startDate`, `endDate` |
| `getWorkRequestsCount` | PUT | `/work/getWorkRequestsCount` | `filters` |
| `myAccomplishments` | GET | `/work/myAccomplishments` | `filters` |
| `myAwaitingFeedbackRequests` | GET | `/work/myAwaitingFeedbackRequests` | `filters` |
| `myCompletedRequests` | GET | `/work/myCompletedRequests` | `filters` |
| `myOpenRequests` | GET | `/work/myOpenRequests` | `filters` |
| `myWork` | GET | `/work/myWork` | `filters` |
| `teamRequestCount` | PUT | `/work/teamRequestCount` | `filters` |
| `teamRequests` | GET | `/work/teamRequests` | `filters` |
| `teamRequestsCount` | PUT | `/work/teamRequestsCount` | — |
| `workItemStatusLabels` | PUT | `/work/workItemStatusLabels` | `items` |
| `workRequests` | GET | `/work/workRequests` | `filters` |


## `/workitem` — WorkItem


*1 named actions.*


| Action | Method | Path | Query parameters |
|---|---|---|---|
| `markViewed` | PUT | `/workitem/markViewed` | `ID` |


---

Source: `AdobeDocs/workfront-apis` `static/workflow.json`, Adobe Workfront API v19.0 (MIT).
Regenerate with `python3 skills/workfront-api/scripts/api_actions.py generate`.

