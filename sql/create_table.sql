create table institution
(
    inst_id   bigint unsigned auto_increment comment '机构ID（主键）'
        primary key,
    inst_name varchar(100) not null comment '机构名称',
    inst_type varchar(30)  not null comment '机构类型：公募/私募/券商/保险',
    constraint uk_inst_name
        unique (inst_name)
)
    comment '机构维度主表' charset = utf8mb4;

create table stock_basic
(
    stock_id    bigint unsigned auto_increment comment '股票唯一ID（主键）'
        primary key,
    stock_code  varchar(20)                        not null comment '股票代码（如600000.SH）',
    stock_name  varchar(50)                        not null comment '股票名称',
    exchange    varchar(10)                        not null comment '交易所：SH/SZ/BJ',
    industry    varchar(50)                        not null comment '所属行业',
    plate       varchar(30)                        not null comment '所属板块',
    create_time datetime default CURRENT_TIMESTAMP not null,
    update_time datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP,
    constraint uk_stock_code
        unique (stock_code)
)
    comment '股票基础信息主表' charset = utf8mb4;

create index idx_industry
    on stock_basic (industry);

create table stock_inst_hold_3
(
    id          bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id    bigint unsigned not null comment '关联股票主表ID',
    inst_id     bigint unsigned not null comment '关联机构主表ID',
    hold_volume bigint          not null comment '持仓数量（股）',
    hold_ratio  decimal(5, 2)   not null comment '持仓占流通股比例（%）',
    hold_cost   decimal(10, 2)  not null comment '持仓成本（元）',
    constraint fk_hold_inst
        foreign key (inst_id) references institution (inst_id)
            on update cascade on delete cascade,
    constraint fk_hold_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '机构持仓表3' charset = utf8mb4;

create index idx_stock_inst
    on stock_inst_hold_3 (stock_id, inst_id);

create table trade_date
(
    date_id        bigint unsigned auto_increment comment '日期ID（主键）'
        primary key,
    trade_date     date    not null comment '交易日期',
    is_trading_day tinyint not null comment '是否交易日：1=是，0=否',
    constraint uk_trade_date
        unique (trade_date)
)
    comment '交易日期维度主表' charset = utf8mb4;

create table stock_daily_trade_1
(
    id        bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id  bigint unsigned not null comment '关联股票主表ID',
    date_id   bigint unsigned not null comment '关联交易日期ID',
    price     decimal(10, 2)  not null comment '当日收盘价',
    rise_fall decimal(5, 2)   not null comment '涨跌幅（%）',
    volume    bigint          not null comment '成交量（手）',
    turnover  decimal(15, 2)  not null comment '成交额（万元）',
    constraint fk_trade_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_trade_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票当日交易表1' charset = utf8mb4;

create index idx_stock_date
    on stock_daily_trade_1 (stock_id, date_id);

create table stock_dividend_4
(
    id               bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id         bigint unsigned not null comment '关联股票主表ID',
    date_id          bigint unsigned not null comment '分红公告日期ID',
    dividend_cash    decimal(10, 2)  not null comment '每股现金分红（元）',
    dividend_stock   decimal(5, 2)   not null comment '每股送转股数',
    ex_dividend_date date            not null comment '除权除息日',
    constraint fk_div_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_div_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票分红表4' charset = utf8mb4;

create index idx_stock_date
    on stock_dividend_4 (stock_id, date_id);

create table stock_dragon_list_6
(
    id          bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id    bigint unsigned not null comment '关联股票主表ID',
    date_id     bigint unsigned not null comment '关联交易日期ID',
    inst_id     bigint unsigned not null comment '上榜机构ID',
    buy_amount  decimal(15, 2)  not null comment '买入金额（万元）',
    sell_amount decimal(15, 2)  not null comment '卖出金额（万元）',
    constraint fk_dragon_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_dragon_inst
        foreign key (inst_id) references institution (inst_id)
            on update cascade on delete cascade,
    constraint fk_dragon_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票龙虎榜表6' charset = utf8mb4;

create index idx_stock_date_inst
    on stock_dragon_list_6 (stock_id, date_id, inst_id);

create table stock_finance_9
(
    id       bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id bigint unsigned not null comment '关联股票主表ID',
    date_id  bigint unsigned not null comment '财报发布日期ID',
    revenue  decimal(20, 2)  not null comment '营业收入（亿元）',
    profit   decimal(20, 2)  not null comment '净利润（亿元）',
    roe      decimal(5, 2)   not null comment '净资产收益率（%）',
    constraint fk_finance_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_finance_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票财务指标表9' charset = utf8mb4;

create index idx_stock_date
    on stock_finance_9 (stock_id, date_id);

create table stock_margin_5
(
    id             bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id       bigint unsigned not null comment '关联股票主表ID',
    date_id        bigint unsigned not null comment '关联交易日期ID',
    margin_buy     decimal(15, 2)  not null comment '融资买入额（万元）',
    margin_sell    decimal(15, 2)  not null comment '融券卖出额（万元）',
    margin_balance decimal(15, 2)  not null comment '融资余额（万元）',
    constraint fk_margin_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_margin_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票融资融券表5' charset = utf8mb4;

create index idx_stock_date
    on stock_margin_5 (stock_id, date_id);

create table stock_market_cap_2
(
    id         bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id   bigint unsigned not null comment '关联股票主表ID',
    date_id    bigint unsigned not null comment '关联交易日期ID',
    market_cap decimal(20, 2)  not null comment '总市值（亿元）',
    pe_ratio   decimal(10, 2)  not null comment '市盈率（TTM）',
    pb_ratio   decimal(10, 2)  not null comment '市净率',
    constraint fk_cap_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_cap_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票市值表2' charset = utf8mb4;

create index idx_stock_date
    on stock_market_cap_2 (stock_id, date_id);

create table stock_north_capital_8
(
    id         bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id   bigint unsigned not null comment '关联股票主表ID',
    date_id    bigint unsigned not null comment '关联交易日期ID',
    north_buy  decimal(15, 2)  not null comment '北向资金买入（万元）',
    north_sell decimal(15, 2)  not null comment '北向资金卖出（万元）',
    north_net  decimal(15, 2)  not null comment '北向资金净买入（万元）',
    constraint fk_north_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_north_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票北向资金表8' charset = utf8mb4;

create index idx_stock_date
    on stock_north_capital_8 (stock_id, date_id);

create table stock_public_opinion_10
(
    id              bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id        bigint unsigned not null comment '关联股票主表ID',
    date_id         bigint unsigned not null comment '舆情日期ID',
    sentiment_score decimal(5, 2)   not null comment '舆情情感分（-5~5）',
    news_count      int             not null comment '相关新闻数量',
    positive_ratio  decimal(5, 2)   not null comment '正面新闻占比（%）',
    constraint fk_opinion_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_opinion_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票舆情表10' charset = utf8mb4;

create index idx_stock_date
    on stock_public_opinion_10 (stock_id, date_id);

create table stock_unlock_7
(
    id            bigint unsigned auto_increment comment '主键ID'
        primary key,
    stock_id      bigint unsigned not null comment '关联股票主表ID',
    date_id       bigint unsigned not null comment '解禁公告日期ID',
    unlock_volume bigint          not null comment '解禁数量（股）',
    unlock_ratio  decimal(5, 2)   not null comment '解禁占总股本比例（%）',
    unlock_type   varchar(50)     not null comment '解禁类型：首发原股东/定增/股权激励',
    constraint fk_unlock_date
        foreign key (date_id) references trade_date (date_id)
            on update cascade on delete cascade,
    constraint fk_unlock_stock
        foreign key (stock_id) references stock_basic (stock_id)
            on update cascade on delete cascade
)
    comment '股票限售解禁表7' charset = utf8mb4;

create index idx_stock_date
    on stock_unlock_7 (stock_id, date_id);

